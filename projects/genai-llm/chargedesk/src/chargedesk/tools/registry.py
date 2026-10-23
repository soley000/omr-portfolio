"""Les outils de l'agent ChargeDesk.

Chaque outil :
- a ses arguments controles par un modele Pydantic (une erreur est renvoyee au LLM
  sous forme de message, jamais sous forme de plantage) ;
- lit l'entrepot UNIQUEMENT par la vue "soir courant" (snapshot) : il ne peut pas voir le futur ;
- applique les definitions metier (periodes, "muette", "fiabilite"...) une seule fois, dans le code ;
- calcule lui-meme les chiffres utiles (taux, ecarts, comptes) : le LLM n'a rien a calculer.
"""
from __future__ import annotations

import json

import duckdb
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from chargedesk.guards.sql import ALLOWED_TABLES, SQLRejected, run_checked
from chargedesk.tools.periods import PeriodError, PeriodName, resolve_period

Metric = Literal["hw_faults", "sessions", "hw_fault_rate", "energy_kwh", "episodes"]
Model = Literal["champion", "fallback"]
UNITS = {"hw_faults": "count", "sessions": "count", "hw_fault_rate": "rate",
         "energy_kwh": "kwh", "episodes": "count"}
REPLAY_FIRST = date(2021, 8, 31)
SILENT_DAYS = 7


class ToolError(ValueError):
    pass


# ----------------------------------------------------------------- arguments
class Scope(BaseModel):
    site: str | None = Field(None, description="Nom exact du site. Vide avec post_id vide = tout le reseau.")
    post_id: int | None = Field(None, ge=1, le=92, description="Numero de borne (1 a 92).")


class PeriodArgs(BaseModel):
    period: PeriodName = Field(description="Periode nommee (relative au soir courant) ou custom.")
    start: date | None = Field(None, description="Debut si period=custom (AAAA-MM-JJ).")
    end: date | None = Field(None, description="Fin si period=custom (AAAA-MM-JJ).")
    years_back: int = Field(0, ge=0, le=1, description="1 = memes dates un an plus tot.")


class GetMetric(Scope, PeriodArgs):
    """Valeur d'un indicateur pour un site, une borne ou tout le reseau, sur une periode."""
    metric: Metric = Field(description="hw_faults (pannes materielles), sessions (recharges), "
                                       "hw_fault_rate (taux de pannes, 0 a 1), energy_kwh, episodes (episodes anormaux).")


class ComparePeriods(Scope):
    """Compare un indicateur sur deux periodes (calcule l'ecart). Pour 'ce mois-ci contre le mois dernier',
    'cette semaine contre la precedente', 'par rapport a l'an dernier'."""
    metric: Metric
    period_a: PeriodName = Field(description="Premiere periode (en general la plus recente).")
    start_a: date | None = None
    end_a: date | None = None
    years_back_a: int = Field(0, ge=0, le=1)
    period_b: PeriodName = Field(description="Periode de comparaison.")
    start_b: date | None = None
    end_b: date | None = None
    years_back_b: int = Field(0, ge=0, le=1)


class GetEveningList(BaseModel):
    """Liste des bornes a inspecter (top 10) produite un soir : rang, borne, site, score. Par defaut ce soir."""
    model: Model = Field("champion", description="champion = modele ChargeTriage ; fallback = regle simple (pannes sur 7 jours).")
    evening: date | None = Field(None, description="Soir de la liste (par defaut le soir courant).")


class GetPostSignals(BaseModel):
    """Signaux d'une borne un soir donne, pour expliquer son score : pannes sur 1, 3, 7, 28 jours, taux, niveau habituel,
    jours depuis le dernier episode, recharges, jours sans recharge, rang et score dans la liste."""
    post_id: int = Field(ge=1, le=92)
    evening: date | None = Field(None, description="Par defaut le soir courant.")


class CompareModelLists(BaseModel):
    """Bornes communes et differentes entre la liste du modele (champion) et celle de la regle simple (fallback)."""
    evening: date | None = Field(None, description="Par defaut le soir courant.")


class GetPostStatus(Scope):
    """Etat d'activite AU SOIR COURANT : derniere recharge, jours sans recharge, borne muette (aucune recharge
    sur les 7 derniers jours). Pour 'fonctionne encore ?', 'a l'arret ?', 'muette ?', 'depuis combien de jours ?'.
    SANS site ni post_id : tout le reseau en un seul appel, avec n_silent (nombre de bornes muettes) et leur liste.
    C'est l'outil pour 'combien / quelles bornes sans recharge depuis 7 jours'."""


class GetSilentAlerts(PeriodArgs):
    """Alertes 'borne muette' LEVEES pendant une periode (une alerte n'est pas un etat : pour savoir si une borne
    est encore muette, utiliser get_post_status)."""


class GetListReliability(BaseModel):
    """Fiabilite recente de la liste : part des bornes listees ayant eu un episode le lendemain, sur les listes
    des 28 soirs precedents dont le resultat est connu, pour le modele et pour la regle simple."""


class GetListHits(BaseModel):
    """Resultat d'une liste passee : combien de bornes listees ont vraiment eu un episode le lendemain,
    et LESQUELLES (detail borne par borne de la liste du modele)."""
    evening: date = Field(description="Soir de la liste (avant le soir courant, ex. hier).")


class RankPosts(PeriodArgs):
    """Classe les bornes selon un indicateur sur une periode : les plus touchees d'abord. Pour 'quelles bornes
    ont le plus de pannes / le plus fort taux de pannes / le moins de recharges...'. Un site peut etre precise."""
    metric: Metric = Field(description="Indicateur de classement (voir get_metric).")
    site: str | None = Field(None, description="Limiter a un site (vide = tout le reseau).")
    top: int = Field(10, ge=1, le=20, description="Nombre de bornes a renvoyer.")
    ascending: bool = Field(False, description="true = les plus faibles d'abord (ex. le moins de recharges).")
    min_sessions: int = Field(20, ge=0, description="Pour un taux : ignorer les bornes avec trop peu de recharges.")


class GetDrift(BaseModel):
    """Derive des variables du modele (PSI) pour le dernier mois termine : stable, watch ou drift."""


class RunSQL(BaseModel):
    """DERNIER RECOURS si aucun autre outil ne convient : une requete SELECT sur les tables marts.*
    (vue du soir courant, lecture seule, 200 lignes au plus)."""
    query: str


# ----------------------------------------------------------------- helpers
def _scope_sql(scope: Scope) -> tuple[str, list]:
    if scope.site and scope.post_id:
        raise ToolError("donner site OU post_id, pas les deux")
    if scope.post_id:
        return "post_id = ?", [scope.post_id]
    if scope.site:
        return "site = ?", [scope.site]
    return "true", []


def _scope_label(scope: Scope) -> str:
    return f"borne {scope.post_id}" if scope.post_id else (scope.site or "tout le reseau")


def _check_site(con, scope: Scope) -> None:
    if scope.site:
        sites = [r[0] for r in con.execute("select site from marts.dim_site order by site").fetchall()]
        if scope.site not in sites:
            raise ToolError(f"site inconnu : {scope.site}. Sites : {', '.join(sites)}")


def _metric_value(con, metric: str, scope: Scope, a: date, b: date) -> dict:
    where, params = _scope_sql(scope)
    row = con.execute(
        f"select sum(n_hw_faults), sum(n_sessions), sum(energy_kwh), "
        f"count(*) filter (where is_episode) from marts.fct_post_day "
        f"where {where} and day between ? and ?", params + [a, b]).fetchone()
    faults, sessions, energy, episodes = (row[0] or 0, row[1] or 0, row[2] or 0.0, row[3] or 0)
    value = {"hw_faults": faults, "sessions": sessions, "energy_kwh": round(float(energy), 3),
             "episodes": episodes,
             "hw_fault_rate": (faults / sessions) if sessions else None}[metric]
    out = {"metric": metric, "unit": UNITS[metric], "scope": _scope_label(scope),
           "start": a.isoformat(), "end": b.isoformat(), "value": value}
    if metric == "hw_fault_rate":
        out.update({"hw_faults": faults, "sessions": sessions})
    return out


def _evening(arg: date | None, current: date) -> date:
    e = arg or current
    if e > current:
        raise ToolError(f"{e} est apres le soir courant {current} : inconnu")
    return e


# ----------------------------------------------------------------- outils
def get_metric(con, current: date, a: GetMetric) -> dict:
    _check_site(con, a)
    start, end = resolve_period(current, a.period, a.start, a.end, a.years_back)
    return _metric_value(con, a.metric, a, start, end)


def compare_periods(con, current: date, a: ComparePeriods) -> dict:
    _check_site(con, a)
    pa = resolve_period(current, a.period_a, a.start_a, a.end_a, a.years_back_a)
    pb = resolve_period(current, a.period_b, a.start_b, a.end_b, a.years_back_b)
    va, vb = _metric_value(con, a.metric, a, *pa), _metric_value(con, a.metric, a, *pb)
    out = {"metric": a.metric, "unit": UNITS[a.metric], "scope": _scope_label(a),
           "period_a": {"start": va["start"], "end": va["end"], "value": va["value"]},
           "period_b": {"start": vb["start"], "end": vb["end"], "value": vb["value"]}}
    if va["value"] is not None and vb["value"] is not None:
        diff = va["value"] - vb["value"]
        out["difference_a_minus_b"] = round(diff, 6) if isinstance(diff, float) else diff
        out["direction"] = "hausse" if diff > 0 else "baisse" if diff < 0 else "stable"
    return out


def get_evening_list(con, current: date, a: GetEveningList) -> dict:
    e = _evening(a.evening, current)
    if e < REPLAY_FIRST:
        raise ToolError(f"aucune liste avant le {REPLAY_FIRST}")
    rows = con.execute(
        "select rank, post_id, site, round(score, 4), episode_next_day from marts.fct_evening_list "
        "where evening = ? and model = ? order by rank", [e, a.model]).fetchall()
    items = [{"rank": r[0], "post_id": r[1], "site": r[2], "score": r[3],
              **({"episode_next_day": r[4]} if r[4] is not None else {})} for r in rows]
    by_site: dict[str, int] = {}
    for it in items:
        by_site[it["site"]] = by_site.get(it["site"], 0) + 1
    return {"evening": e.isoformat(), "model": a.model, "n_listed": len(items), "list": items,
            "posts_per_site": by_site,
            "note": "score = risque estime d'un episode le lendemain (0 a 1)"
                    + ("" if e < current else " ; resultat du lendemain pas encore connu")}


def get_post_signals(con, current: date, a: GetPostSignals) -> dict:
    e = _evening(a.evening, current)
    row = con.execute(
        "select s.site, s.hw_faults_d0, s.hw_faults_3d, s.hw_faults_7d, s.hw_faults_28d, "
        "round(s.hw_rate_7d, 4), round(s.hw_rate_28d, 4), s.sessions_7d, s.idle_days_7d, s.episodes_28d, "
        "s.days_since_episode, round(d.baseline_rate, 4) "
        "from marts.fct_post_evening s left join marts.fct_post_day d on d.post_id = s.post_id and d.day = s.evening "
        "where s.post_id = ? and s.evening = ?", [a.post_id, e]).fetchone()
    if row is None:
        raise ToolError(f"aucun signal pour la borne {a.post_id} le {e}")
    keys = ["site", "hw_faults_today", "hw_faults_3d", "hw_faults_7d", "hw_faults_28d", "hw_rate_7d",
            "hw_rate_28d", "sessions_7d", "days_without_recharge_7d", "episodes_28d",
            "days_since_last_episode", "usual_hw_rate_28d_before"]
    out = {"post_id": a.post_id, "evening": e.isoformat(), **dict(zip(keys, row))}
    for model in ("champion", "fallback"):
        r = con.execute("select rank, round(score, 4) from marts.fct_evening_list "
                        "where evening = ? and model = ? and post_id = ?", [e, model, a.post_id]).fetchone()
        out[f"in_{model}_list"] = {"rank": r[0], "score": r[1]} if r else None
    out["note"] = ("Ces signaux expliquent le SCORE du modele ; ils ne disent pas la CAUSE des pannes. "
                   "days_since_last_episode vaut 365 si aucun episode depuis 2020.")
    return out


def compare_model_lists(con, current: date, a: CompareModelLists) -> dict:
    e = _evening(a.evening, current)
    lists = {m: [r[0] for r in con.execute("select post_id from marts.fct_evening_list "
                                           "where evening = ? and model = ? order by rank", [e, m]).fetchall()]
             for m in ("champion", "fallback")}
    common = [p for p in lists["champion"] if p in lists["fallback"]]
    return {"evening": e.isoformat(), "n_common": len(common), "common_posts": common,
            "only_champion": [p for p in lists["champion"] if p not in common],
            "only_fallback": [p for p in lists["fallback"] if p not in common]}


def get_post_status(con, current: date, a: GetPostStatus) -> dict:
    _check_site(con, a)
    where, params = _scope_sql(a)
    rows = con.execute(
        f"select post_id, site, max(case when n_sessions > 0 then day end) from marts.fct_post_day "
        f"where {where} group by post_id, site order by post_id", params).fetchall()
    posts = []
    for pid, site, last in rows:
        days = (current - last).days if last else None
        posts.append({"post_id": pid, "site": site, "last_recharge": last.isoformat() if last else None,
                      "days_without_recharge": days, "silent": days is None or days >= SILENT_DAYS})
    lasts = [p["last_recharge"] for p in posts if p["last_recharge"]]
    last_any = max(lasts) if lasts else None
    return {"evening": current.isoformat(), "scope": _scope_label(a), "n_posts": len(posts),
            "n_silent": sum(p["silent"] for p in posts),
            "last_recharge_in_scope": last_any,
            "days_since_last_recharge_in_scope": (current - date.fromisoformat(last_any)).days if last_any else None,
            "definition": f"muette = aucune recharge sur les {SILENT_DAYS} derniers jours",
            "posts": posts if len(posts) <= 20 else [p for p in posts if p["silent"]]}


def get_silent_alerts(con, current: date, a: GetSilentAlerts) -> dict:
    start, end = resolve_period(current, a.period, a.start, a.end, a.years_back)
    rows = con.execute("select post_id, site, alert_date, last_session_date from marts.fct_silent_alert "
                       "where alert_date between ? and ? order by alert_date, post_id", [start, end]).fetchall()
    return {"start": start.isoformat(), "end": end.isoformat(), "n_alerts": len(rows),
            "alerts": [{"post_id": r[0], "site": r[1], "alert_date": r[2].isoformat(),
                        "last_recharge": r[3].isoformat()} for r in rows],
            "note": "alertes levees dans la periode ; l'etat actuel se lit avec get_post_status"}


def get_list_reliability(con, current: date, a: GetListReliability) -> dict:
    first, last = current - timedelta(28), current - timedelta(1)
    out = {"evenings": f"{first.isoformat()} a {last.isoformat()}",
           "definition": "part des bornes listees ayant eu un episode le lendemain (resultats connus)"}
    for model in ("champion", "fallback"):
        r = con.execute("select count(*), sum(n_hits), sum(n_listed - n_unknown) from marts.fct_list_daily_hits "
                        "where model = ? and evening between ? and ?", [model, first, last]).fetchone()
        n_ev, hits, known = r[0], r[1] or 0, r[2] or 0
        out[model] = {"n_evenings": n_ev, "hits": hits, "known_outcomes": known,
                      "reliability": (hits / known) if known else None}
    return out


def get_list_hits(con, current: date, a: GetListHits) -> dict:
    if a.evening >= current:
        raise ToolError(f"le resultat de la liste du {a.evening} n'est connu que le lendemain")
    out = {"evening": a.evening.isoformat()}
    for model in ("champion", "fallback"):
        r = con.execute("select n_listed, n_hits, n_unknown from marts.fct_list_daily_hits "
                        "where model = ? and evening = ?", [model, a.evening]).fetchone()
        if r is None:
            raise ToolError(f"aucune liste le {a.evening}")
        out[model] = {"n_listed": r[0], "n_hits": r[1], "n_unknown": r[2]}
    rows = con.execute("select rank, post_id, site, episode_next_day from marts.fct_evening_list "
                       "where model = 'champion' and evening = ? order by rank", [a.evening]).fetchall()
    out["champion_posts"] = [{"rank": rk, "post_id": pid, "site": site,
                              "episode_next_day": None if ep is None else bool(ep)} for rk, pid, site, ep in rows]
    return out


def rank_posts(con, current: date, a: RankPosts) -> dict:
    scope = Scope(site=a.site)
    _check_site(con, scope)
    start, end = resolve_period(current, a.period, a.start, a.end, a.years_back)
    where, params = _scope_sql(scope)
    rows = con.execute(
        f"select post_id, site, sum(n_hw_faults), sum(n_sessions), sum(energy_kwh), "
        f"count(*) filter (where is_episode) from marts.fct_post_day "
        f"where {where} and day between ? and ? group by post_id, site", params + [start, end]).fetchall()
    items = []
    for pid, site, faults, sessions, energy, episodes in rows:
        faults, sessions = faults or 0, sessions or 0
        if a.metric == "hw_fault_rate" and sessions < a.min_sessions:
            continue
        value = {"hw_faults": faults, "sessions": sessions, "energy_kwh": round(float(energy or 0), 3),
                 "episodes": episodes or 0, "hw_fault_rate": (faults / sessions) if sessions else None}[a.metric]
        items.append({"post_id": pid, "site": site, "value": value, "hw_faults": faults, "sessions": sessions})
    items.sort(key=lambda x: (x["value"] is None, x["value"] if a.ascending else -(x["value"] or 0), x["post_id"]))
    ranked = [{"rank": i + 1, **x} for i, x in enumerate(items[:a.top])]
    out = {"metric": a.metric, "unit": UNITS[a.metric], "scope": _scope_label(scope),
           "start": start.isoformat(), "end": end.isoformat(), "posts": ranked}
    if a.metric == "hw_fault_rate":
        out["note"] = f"bornes avec moins de {a.min_sessions} recharges sur la periode ignorees (taux peu fiable)"
    return out


def get_drift(con, current: date, a: GetDrift) -> dict:
    rows = con.execute("select month, feature, round(psi, 3), level from marts.fct_drift_month "
                       "where month = (select max(month) from marts.fct_drift_month) order by psi desc").fetchall()
    if not rows:
        return {"note": "aucun mois de derive termine a ce soir"}
    return {"month": rows[0][0], "n_drift": sum(r[3] == "drift" for r in rows),
            "features": [{"feature": r[1], "psi": r[2], "level": r[3]} for r in rows]}


def run_sql(con, current: date, a: RunSQL) -> dict:
    try:
        rows = run_checked(con, a.query)
    except SQLRejected as exc:
        raise ToolError(str(exc)) from exc
    except duckdb.Error as exc:   # colonne inconnue, faute de syntaxe... : renvoye au LLM avec le schema
        cols = con.execute("select table_name, string_agg(column_name, ', ' order by ordinal_position) "
                           "from information_schema.columns where table_schema = 'marts' "
                           "and table_catalog = current_database() "
                           "group by table_name order by table_name").fetchall()
        allowed = {a.split(".")[-1] for a in ALLOWED_TABLES}
        schema = " | ".join(f"marts.{tname}({c})" for tname, c in dict(cols).items() if tname in allowed)
        raise ToolError(f"erreur SQL : {str(exc).splitlines()[0][:300]}. Colonnes disponibles : {schema}") from exc
    return {"n_rows": len(rows), "rows": rows}


TOOLS = {
    "get_metric": (GetMetric, get_metric),
    "compare_periods": (ComparePeriods, compare_periods),
    "get_evening_list": (GetEveningList, get_evening_list),
    "get_post_signals": (GetPostSignals, get_post_signals),
    "compare_model_lists": (CompareModelLists, compare_model_lists),
    "get_post_status": (GetPostStatus, get_post_status),
    "get_silent_alerts": (GetSilentAlerts, get_silent_alerts),
    "get_list_reliability": (GetListReliability, get_list_reliability),
    "get_list_hits": (GetListHits, get_list_hits),
    "rank_posts": (RankPosts, rank_posts),
    "get_drift": (GetDrift, get_drift),
    "run_sql": (RunSQL, run_sql),
}


def _clean(schema):
    """Schema Pydantic -> schema simple accepte par tous les fournisseurs (pas de titres, ni anyOf avec null)."""
    if isinstance(schema, dict):
        if "anyOf" in schema:
            options = [o for o in schema["anyOf"] if o.get("type") != "null"]
            merged = {**options[0], **{k: v for k, v in schema.items() if k not in ("anyOf", "default", "title")}}
            return _clean(merged)
        return {k: _clean(v) for k, v in schema.items() if k not in ("title", "default")}
    if isinstance(schema, list):
        return [_clean(v) for v in schema]
    return schema


def tool_specs() -> list[dict]:
    specs = []
    for name, (model, _) in TOOLS.items():
        params = _clean(model.model_json_schema())
        params.setdefault("properties", {})
        params.pop("description", None)
        params["type"] = "object"
        specs.append({"type": "function", "function": {
            "name": name, "description": " ".join((model.__doc__ or "").split()), "parameters": params}})
    return specs


def call_tool(con, current: date, name: str, raw_args: str | dict) -> tuple[bool, dict]:
    """Execute un outil. Renvoie (succes, resultat) ; en cas d'erreur, resultat = {'error': message lisible}."""
    if name not in TOOLS:
        return False, {"error": f"outil inconnu : {name}. Outils : {', '.join(TOOLS)}"}
    model, fn = TOOLS[name]
    try:
        args = json.loads(raw_args or "{}") if isinstance(raw_args, str) else (raw_args or {})
        parsed = model(**args)
        return True, fn(con, current, parsed)
    except json.JSONDecodeError as exc:
        return False, {"error": f"arguments illisibles (JSON) : {exc}"}
    except ValidationError as exc:
        msgs = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5])
        return False, {"error": f"arguments invalides : {msgs}"}
    except (ToolError, PeriodError) as exc:
        return False, {"error": str(exc)}
    except Exception as exc:  # filet : un outil ne doit jamais faire tomber l'agent
        return False, {"error": f"erreur interne de l'outil {name} ({type(exc).__name__}) : {str(exc)[:200]}"}
