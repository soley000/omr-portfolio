"""MobilityFlow : tableau de bord du réseau Bicloo (Nantes).

Lancement (depuis la racine du projet) :
    streamlit run app/streamlit_app.py

Il lit, en lecture seule, la base de données (DuckDB) construite chaque nuit par Airflow + dbt.
Il ne contient aucune logique de collecte ni de nettoyage : tout ça est fait en amont.
Les textes sont volontairement écrits en langage courant, sans jargon technique.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent))
import data as dq  # noqa: E402  (couche d'accès aux données)

# Couleurs : chaque état a aussi son nom écrit (la couleur ne porte jamais seule l'information).
GOOD, NO_BIKE, NO_DOCK, BOTH, GREY = "#2FA37A", "#F08A3C", "#3C7BC4", "#8E5BB5", "#9AA9A7"
INK, MUTED, LINE, ACCENT = "#12333A", "#4B6A70", "#DCE6E4", "#0F8B8D"
FREQUENT = 0.20            # « manque régulièrement » = au moins 20 % du temps (1 mesure sur 5)
MIN_MEASURES = 100         # en dessous (≈ 1 h 40), pas assez de mesures pour juger une station sur la journée
MIN_MEASURES_HOUR = 10     # idem pour une heure précise
VERDICT_COLOR = {"Bien équilibrée": GOOD, "Manque de vélos": NO_BIKE, "Manque de places": NO_DOCK,
                 "Les deux": BOTH, "Pas assez de mesures": GREY}
BIKE_SVG = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" '
            'stroke-linecap="round" stroke-linejoin="round"><circle cx="5.5" cy="17" r="3.5"/>'
            '<circle cx="18.5" cy="17" r="3.5"/><path d="M5.5 17l4-8h5l4 8M9.5 9L12 17M14 5h3"/></svg>')

st.set_page_config(page_title="MobilityFlow · Bicloo Nantes", page_icon="🚲", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=DM+Sans:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'DM Sans', system-ui, sans-serif; }}
h1, h2, h3 {{ font-family: 'Bricolage Grotesque', sans-serif !important; color: {INK}; }}
.block-container {{ padding-top: 1.6rem; max-width: 1280px; }}
.mf-banner {{ background:{INK}; color:#fff; border-radius:16px; padding:18px 22px; margin:6px 0 14px 0; }}
.mf-banner .q {{ font-size:13px; opacity:.7; }}
.mf-banner .a {{ font-family:'Bricolage Grotesque',sans-serif; font-size:22px; font-weight:600; line-height:1.3; margin-top:4px; }}
.mf-banner .m {{ font-size:14px; line-height:1.5; margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,.2); }}
.mf-banner .m b {{ color:#F6B67F; }}
.mf-card {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:18px 20px; height:100%; }}
.mf-card .t {{ font-weight:700; font-size:17px; display:flex; align-items:center; gap:10px; }}
.mf-card .d {{ width:12px; height:12px; border-radius:50%; display:inline-block; }}
.mf-card .s {{ font-size:13px; color:{MUTED}; margin:6px 0 10px 0; }}
.mf-card .b {{ font-size:15px; line-height:1.7; }}
.mf-card .f {{ font-size:13px; color:{MUTED}; margin-top:10px; }}
.mf-kpi {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:16px 20px; height:100%; }}
.mf-kpi .l {{ font-size:14px; font-weight:700; color:{INK}; }}
.mf-kpi .v {{ font-family:'Bricolage Grotesque',sans-serif; font-size:34px; font-weight:700; margin-top:2px; }}
.mf-kpi .h {{ font-size:13px; color:{MUTED}; line-height:1.4; }}
.mf-note {{ font-size:13px; color:{MUTED}; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- chargement
@st.cache_data(show_spinner="Lecture de la base de données…")
def load(path: str, mtime: float) -> dict[str, pd.DataFrame]:
    # `mtime` n'est utilisé que pour la clé de cache : quand Airflow republie le fichier
    # (nouvelle date de modification), le cache est invalidé tout seul.
    return dq.load_warehouse(path)


wh = dq.warehouse_path()
if not wh.exists():
    st.error(f"Base de données introuvable : {wh}")
    st.info("Lance d'abord le traitement de nuit (DAG mobilityflow_daily dans Airflow) pour créer "
            "`mobilityflow.duckdb`, ou indique son emplacement avec MOBILITYFLOW_WAREHOUSE_PATH.")
    st.stop()

try:
    T = load(str(wh), wh.stat().st_mtime)
except Exception as exc:  # fichier en cours de remplacement, table manquante, etc.
    st.error("Impossible de lire la base de données pour le moment. Réessaie dans une minute.")
    st.caption(f"Détail technique : {exc}")
    st.stop()

stations, hours, collection, unchanged, meta = T["stations"], T["hours"], T["collection"], T["unchanged"], T["meta"].iloc[0]
if hours.empty:
    st.warning("La base existe mais ne contient pas encore de mesures.")
    st.stop()

hours["date_paris"] = pd.to_datetime(hours["date_paris"]).dt.date
collection["date_paris"] = pd.to_datetime(collection["date_paris"]).dt.date
first_date, last_date = min(hours["date_paris"]), max(hours["date_paris"])
n_days = int(meta["days"])
first_snap, last_snap = pd.to_datetime(meta["first_snapshot"]), pd.to_datetime(meta["last_snapshot"])
name_of = stations.set_index("station_id")["name"].to_dict()
# Certaines stations ont une coordonnée à 0 dans l'API (ex. (0, 0)) : on les écarte de la carte et on les signale.
# Une latitude ou une longitude égale à 0 pile n'existe pas à Nantes (lat ~47, lon ~-1,5).
geo_ok = stations["lat"].notna() & stations["lon"].notna() & (stations["lat"] != 0) & (stations["lon"] != 0)
bad_geo = stations[~geo_ok]

# ---------------------------------------------------------------- barre latérale
with st.sidebar:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <div style="width:44px;height:44px;border-radius:14px;background:{ACCENT};display:flex;align-items:center;justify-content:center">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5.5" cy="17" r="3.5"/><circle cx="18.5" cy="17" r="3.5"/><path d="M5.5 17l4-8h5l4 8M9.5 9L12 17M14 5h3"/></svg>
      </div>
      <div style="font-family:'Bricolage Grotesque',sans-serif;font-weight:700;font-size:22px;line-height:1.1">MobilityFlow<br><span style="font-weight:600;font-size:14px;opacity:.7">Bicloo · Nantes</span></div>
    </div>""", unsafe_allow_html=True)
    period = st.date_input("Période étudiée", value=(first_date, last_date), min_value=first_date, max_value=last_date,
                           format="DD/MM/YYYY", help="Choisis un jour de début et un jour de fin.")
    day_type = st.radio("Quels jours ?", ["Tous", "Semaine", "Week-end"], horizontal=True)
    st.markdown("**Couleurs des stations**")
    for colr, txt in [(NO_BIKE, "Manque de vélos"), (NO_DOCK, "Manque de places"), (BOTH, "Les deux"),
                      (GOOD, "Bien équilibrée"), (GREY, "Pas assez de mesures")]:
        st.markdown(f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:{colr};'
                    f'margin-right:8px;vertical-align:middle"></span>{txt}', unsafe_allow_html=True)
    st.caption("« Manque » veut dire : pas de vélo (ou pas de place) pendant au moins un cinquième du temps. "
               "Les définitions sont dans l'onglet « À propos ».")
    st.caption("Données : Bicloo, JCDecaux / Nantes Métropole (Licence Ouverte).")

p_start, p_end = (period[0], period[-1]) if isinstance(period, (tuple, list)) and len(period) else (first_date, last_date)
sel = hours[(hours["date_paris"] >= p_start) & (hours["date_paris"] <= p_end)].copy()
weekday = pd.to_datetime(sel["date_paris"]).dt.weekday
if day_type == "Semaine":
    sel = sel[weekday < 5]
elif day_type == "Week-end":
    sel = sel[weekday >= 5]
sel_days = sel["date_paris"].nunique()


# ---------------------------------------------------------------- petites fonctions d'affichage
def banner(question: str, answer: str, business: str) -> None:
    st.markdown(f'<div class="mf-banner"><div class="q">{question}</div><div class="a">{answer}</div>'
                f'<div class="m"><b>À quoi ça sert :</b> {business}</div></div>', unsafe_allow_html=True)


def kpi(col, label: str, value: str, hint: str, color: str = INK, size: int = 34) -> None:
    col.markdown(f'<div class="mf-kpi"><div class="l">{label}</div><div class="v" style="color:{color};font-size:{size}px">{value}</div>'
                 f'<div class="h">{hint}</div></div>', unsafe_allow_html=True)


def period_caption() -> None:
    st.caption(f"Période étudiée : du {p_start:%d/%m/%Y} au {p_end:%d/%m/%Y} · {day_type.lower()} · "
               f"mesures disponibles du {first_snap:%d/%m à %H h %M} au {last_snap:%d/%m à %H h %M}.")


def confidence_note(days: int) -> None:
    if days < 3:
        st.warning(f"Lecture **indicative** : seulement {days} jour(s) de mesures. Les classements deviendront plus "
                   "solides avec davantage de jours.")
    elif days < 14:
        st.info(f"Lecture **préliminaire** : {days} jours de mesures. Il en faut environ 14 pour comparer "
                "la semaine et le week-end.")
    else:
        st.caption(f"Basé sur {days} jours de mesures.")


def empty_selection() -> bool:
    if sel.empty:
        st.warning("Aucune mesure pour cette sélection (période ou jours choisis). Élargis les choix à gauche.")
        return True
    return False


def verdict(pct_empty: float, pct_full: float, n: float, minimum: int = MIN_MEASURES) -> str:
    if pd.isna(pct_empty) or pd.isna(n) or n < minimum:
        return "Pas assez de mesures"
    no_bike, no_dock = pct_empty >= FREQUENT, pct_full >= FREQUENT
    if no_bike and no_dock:
        return "Les deux"
    return "Manque de vélos" if no_bike else ("Manque de places" if no_dock else "Bien équilibrée")


def station_table(by: str) -> pd.DataFrame:
    g = dq.weighted_rates(sel, ["station_id"])
    g = g[g["snapshots_in_service"] >= MIN_MEASURES].copy()
    g["name"] = g["station_id"].map(name_of)
    g["verdict"] = [verdict(e, f, n) for e, f, n in zip(g["pct_empty"], g["pct_full"], g["snapshots_in_service"])]
    return g.sort_values(by, ascending=False)


def duration_text(frac: float, n: float) -> str:
    """Traduit une part du temps en durée concrète : 0,64 sur 480 mesures -> '5 h 07 sur 8 h 00'."""
    return f"{dq.fmt_minutes(frac * n)} sur {dq.fmt_minutes(n)}"


def style_fig(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans", color=INK),
                      legend=dict(orientation="h", y=-0.2))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E6EEEC")
    return fig


def reception_rate() -> tuple[float, int]:
    """Part des mesures attendues effectivement reçues (hors première et dernière heure, partielles par nature)."""
    part = collection[~collection["is_partial_hour"]]
    if part.empty:
        return float("nan"), 0
    missing = part[part["completeness"] < 0.9]
    return part["snapshots"].sum() / part["expected_snapshots"].sum(), len(missing)


# ---------------------------------------------------------------- en-tête + onglets
st.title("Comment respire le réseau Bicloo ?")
tab_syn, tab_qo, tab_fia, tab_apr = st.tabs(["Synthèse", "Quand et où", "Fiabilité des données", "À propos"])

# ================================================================ SYNTHÈSE
with tab_syn:
    if not empty_selection():
        t = station_table("pct_empty")
        no_bike = t[t["verdict"].isin(["Manque de vélos", "Les deux"])].sort_values("pct_empty", ascending=False).head(3)
        no_dock = t[t["verdict"].isin(["Manque de places", "Les deux"])].sort_values("pct_full", ascending=False).head(2)
        frozen = unchanged[unchanged["looks_frozen_now"]]
        gaps = stations[stations["has_capacity_gap"]]
        rate, n_missing_hours = reception_rate()

        if len(no_bike):
            answer = ("Envoyer des vélos en priorité à : " + ", ".join(no_bike["name"]) + ". "
                      + (f"{len(frozen)} station(s) à contrôler." if len(frozen) else "Aucune panne probable."))
        elif len(t):
            answer = ("Rien d'urgent : aucune station ne manque régulièrement de vélos. "
                      + (f"{len(frozen)} station(s) à contrôler." if len(frozen) else "Aucune panne probable."))
        else:
            answer = "Pas encore assez de mesures pour comparer les stations."
        banner("Que faut-il faire en priorité ?", answer,
               "à décider où envoyer des vélos, quelles stations faire contrôler, et si l'on peut se fier aux chiffres. "
               "Ce sont des pistes indicatives, pas des ordres.")
        period_caption()
        confidence_note(sel_days)

        avg = dq.weighted_rates(sel.assign(g=1), ["g"]).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        kpi(c1, "Stations suivies", f"{int(meta['stations'])}", "Nombre de stations du réseau.")
        kpi(c2, "Bornes occupées", dq.fmt_pct(avg["fill_rate"]), "En moyenne, part des bornes qui ont un vélo.", GOOD)
        kpi(c3, "Temps sans vélo", dq.fmt_pct(avg["pct_empty"], 1), "En moyenne, part du temps où une station n'a aucun vélo.", "#C25E15")
        kpi(c4, "Temps sans place", dq.fmt_pct(avg["pct_full"], 1), "En moyenne, part du temps où une station n'a aucune place libre.", "#2F66A8")
        st.write("")

        a, b, c = st.columns(3)
        lines = "".join(f"<b>{r.name}</b><br><span style='color:{MUTED}'>Pas de vélo {dq.fmt_pct(r.pct_empty)} du temps "
                        f"({duration_text(r.pct_empty, r.snapshots_in_service)})</span><br>" for r in no_bike.itertuples())
        lines_d = "".join(f"<b>{r.name}</b><br><span style='color:{MUTED}'>Pas de place {dq.fmt_pct(r.pct_full)} du temps "
                          f"({duration_text(r.pct_full, r.snapshots_in_service)})</span><br>" for r in no_dock.itertuples())
        a.markdown(f'<div class="mf-card"><div class="t"><span class="d" style="background:{NO_BIKE}"></span>Où envoyer des vélos ?</div>'
                   f'<div class="s">Stations qui manquent régulièrement de vélos</div>'
                   f'<div class="b">{lines or "Aucune station ne manque régulièrement de vélos."}'
                   f'<div style="margin-top:8px;font-weight:700">Où en retirer ?</div>'
                   f'{lines_d or "Aucune station ne manque régulièrement de places."}</div>'
                   f'<div class="f">Pour l\'équipe qui redistribue les vélos.</div></div>', unsafe_allow_html=True)

        if len(frozen):
            body = "".join(f"<b>{name_of.get(r.station_id, r.station_id)}</b><br><span style='color:{MUTED}'>"
                           f"{dq.fmt_minutes(r.current_unchanged_minutes)} sans aucun changement</span><br>" for r in frozen.itertuples())
            head_m = "Stations à faire contrôler"
        else:
            near = unchanged.sort_values("current_unchanged_minutes", ascending=False).head(1)
            body = "<b>Aucune panne probable.</b>"
            if len(near) and pd.notna(near.iloc[0]["current_unchanged_minutes"]):
                r = near.iloc[0]
                body += (f"<br><span style='color:{MUTED}'>À surveiller : {name_of.get(r['station_id'], r['station_id'])}, "
                         f"{dq.fmt_minutes(r['current_unchanged_minutes'])} sans changement.</span>")
            head_m = "Aucune station à contrôler"
        b.markdown(f'<div class="mf-card"><div class="t"><span class="d" style="background:{NO_DOCK}"></span>Quoi faire contrôler ?</div>'
                   f'<div class="s">{head_m} (nombre de vélos inchangé depuis plus de 6 h)</div><div class="b">{body}</div>'
                   f'<div class="f">Pour l\'équipe de maintenance. Une alerte, pas une preuve de panne.</div></div>', unsafe_allow_html=True)

        rate_txt = dq.fmt_pct(rate) if pd.notna(rate) else "n/d"
        c.markdown(f'<div class="mf-card"><div class="t"><span class="d" style="background:{GOOD}"></span>Peut-on se fier aux chiffres ?</div>'
                   f'<div class="s">Ce qu\'il faut savoir avant de décider</div>'
                   f'<div class="b"><b>{rate_txt}</b> des mesures attendues ont été reçues<br>'
                   f'<b>{len(gaps)}</b> station(s) avec un nombre de bornes annoncé inexact<br>'
                   f'<b>{len(bad_geo)}</b> station(s) sans position GPS valide</div>'
                   f'<div class="f">Pour l\'équipe données. Détails dans l\'onglet « Fiabilité des données ».</div></div>', unsafe_allow_html=True)

# ================================================================ QUAND ET OÙ
with tab_qo:
    if not empty_selection():
        t = station_table("pct_empty")
        by_hour = dq.weighted_rates(sel, ["hour_paris"]).sort_values("hour_paris")
        if len(t) and by_hour["pct_empty"].notna().any():
            top = t.iloc[0]
            worst = by_hour.loc[by_hour["pct_empty"].idxmax()]
            lead = (f"{top['name']} n'a pas de vélo {dq.fmt_pct(top['pct_empty'])} du temps ({duration_text(top['pct_empty'], top['snapshots_in_service'])}). "
                    if top["pct_empty"] >= FREQUENT else "Aucune station ne manque régulièrement de vélos. ")
            answer = (lead + f"C'est à {int(worst['hour_paris'])} h que le plus de stations sont sans vélo "
                      f"({dq.fmt_pct(worst['pct_empty'], 1)} d'entre elles).")
        else:
            answer = "Pas encore assez de mesures pour répondre."
        banner("Où et à quelle heure manque-t-il des vélos ou des places ?", answer,
               "à décider où et quand envoyer des vélos, et où il faudrait peut-être plus de bornes.")
        period_caption()
        confidence_note(sel_days)

        st.subheader("Le réseau, station par station")
        hour_opts = ["Toute la journée"] + [f"{h} h" for h in sorted(sel["hour_paris"].unique())]
        choice = st.select_slider("Heure de la journée", options=hour_opts, value="Toute la journée")
        mp = sel if choice == "Toute la journée" else sel[sel["hour_paris"] == int(choice.split()[0])]
        minimum = MIN_MEASURES if choice == "Toute la journée" else MIN_MEASURES_HOUR
        st_map = dq.weighted_rates(mp, ["station_id"]).merge(stations[["station_id", "name", "lat", "lon"]], on="station_id")
        st_map = st_map[st_map["station_id"].isin(stations.loc[geo_ok, "station_id"])]
        # Cadrage calculé ici (et non par fit_bounds) : fit_bounds se trompe quand la carte est dessinée
        # dans un onglet encore caché (taille 0) et donne alors une vue "monde entier".
        lo, hi = st_map[["lat", "lon"]].min(), st_map[["lat", "lon"]].max()  # toutes les stations valides
        centre = [(lo["lat"] + hi["lat"]) / 2, (lo["lon"] + hi["lon"]) / 2]
        lat_span, lon_span = max(hi["lat"] - lo["lat"], 0.005), max(hi["lon"] - lo["lon"], 0.005)
        zoom_lon = math.log2(900 * 360 / (256 * lon_span))
        zoom_lat = math.log2(450 * 360 * math.cos(math.radians(centre[0])) / (256 * lat_span))
        zoom = int(max(9, min(16, math.floor(min(zoom_lon, zoom_lat)))))
        m = folium.Map(location=centre, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
        for r in st_map.itertuples():
            v = verdict(r.pct_empty, r.pct_full, r.snapshots_in_service, minimum)
            if v == "Pas assez de mesures":
                detail = "pas assez de mesures pour juger"
            else:
                detail = (f"on trouve un vélo {dq.fmt_pct(1 - r.pct_empty)} du temps<br>"
                          f"on trouve une place {dq.fmt_pct(1 - r.pct_full)} du temps")
            tip = f"<b>{r.name}</b><br>{v}<br>{detail}"
            html = (f'<div style="width:30px;height:30px;border-radius:50%;background:{VERDICT_COLOR[v]};border:2px solid #fff;'
                    f'display:flex;align-items:center;justify-content:center;box-shadow:0 2px 6px rgba(18,51,58,.35)">{BIKE_SVG}</div>')
            folium.Marker([r.lat, r.lon], icon=folium.DivIcon(html=html, icon_size=(30, 30), icon_anchor=(15, 15)),
                          tooltip=folium.Tooltip(tip)).add_to(m)
        st_folium(m, height=470, use_container_width=True, returned_objects=[])
        st.markdown('<div class="mf-note">Passe la souris sur une pastille pour lire le détail de la station. '
                    'Les couleurs sont expliquées dans la barre de gauche.'
                    + (f' {len(bad_geo)} station(s) sans position GPS valide ne sont pas sur la carte '
                       f'(voir « Fiabilité des données »).' if len(bad_geo) else '') + '</div>', unsafe_allow_html=True)

        st.subheader("Quand : le rythme de la journée")
        st.caption("Pour chaque heure, part des stations du réseau qui sont sans vélo (orange) ou sans place libre (bleu). "
                   "Exemple : une barre orange à 8 % veut dire qu'environ 8 stations sur 100 n'ont aucun vélo à cette heure-là.")
        fig = go.Figure()
        fig.add_bar(x=by_hour["hour_paris"], y=by_hour["pct_empty"], name="Stations sans vélo", marker_color=NO_BIKE)
        fig.add_bar(x=by_hour["hour_paris"], y=by_hour["pct_full"], name="Stations sans place libre", marker_color=NO_DOCK)
        fig.update_layout(barmode="group", yaxis_tickformat=".0%", xaxis_title="Heure de la journée", xaxis=dict(dtick=1))
        st.plotly_chart(style_fig(fig), width="stretch")

        st.subheader("Où : les stations les plus en difficulté")
        left, right = st.columns(2)
        for col, key, colr, title, sub in [
                (left, "pct_empty", NO_BIKE, "Où manque-t-il le plus de vélos ?", "Part du temps sans aucun vélo"),
                (right, "pct_full", NO_DOCK, "Où manque-t-il le plus de places ?", "Part du temps sans aucune place libre")]:
            top10 = t.sort_values(key, ascending=False).head(10).iloc[::-1]
            f = go.Figure(go.Bar(x=top10[key], y=top10["name"], orientation="h", marker_color=colr,
                                 text=[dq.fmt_pct(v) for v in top10[key]], textposition="outside"))
            f.update_layout(xaxis_tickformat=".0%", xaxis_range=[0, max(0.1, float(top10[key].max() or 0) * 1.25)],
                            title=dict(text=title, font=dict(size=15)))
            col.plotly_chart(style_fig(f, 360), width="stretch")
            col.caption(sub + ".")

        st.subheader("Où et quand à la fois")
        st.caption("Plus la case est orange, plus la station est souvent sans vélo à cette heure-là. "
                   "Les stations affichées sont celles qui manquent le plus de vélos.")
        n_show = st.slider("Nombre de stations affichées", 5, 30, 12)
        picks = t.head(n_show)["station_id"].tolist()
        hm = dq.weighted_rates(sel[sel["station_id"].isin(picks)], ["station_id", "hour_paris"])
        hm["name"] = hm["station_id"].map(name_of)
        pv = hm.pivot(index="name", columns="hour_paris", values="pct_empty").reindex([name_of[p] for p in picks])
        fig = go.Figure(go.Heatmap(z=pv.values, x=[f"{h} h" for h in pv.columns], y=pv.index, zmin=0,
                                   colorscale=[[0, "#F6F9F8"], [1, NO_BIKE]], colorbar=dict(title="Sans vélo", tickformat=".0%"),
                                   hovertemplate="%{y}<br>%{x} : sans vélo %{z:.0%} du temps<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style_fig(fig, 60 + 26 * len(picks)), width="stretch")

        st.subheader("Zoom sur une station")
        pick = st.selectbox("Choisis une station", options=stations.sort_values("name")["station_id"], format_func=lambda s: name_of.get(s, s))
        one = sel[sel["station_id"] == pick]
        if one.empty:
            st.info("Pas de mesures pour cette station sur la sélection.")
        else:
            rates = dq.weighted_rates(one.assign(g=1), ["g"]).iloc[0]
            v = verdict(rates["pct_empty"], rates["pct_full"], rates["snapshots_in_service"], MIN_MEASURES_HOUR)
            st.markdown(f"**{name_of.get(pick, pick)}** : {v}. On y trouve un vélo {dq.fmt_pct(1 - rates['pct_empty'])} du temps "
                        f"et une place libre {dq.fmt_pct(1 - rates['pct_full'])} du temps.")
            w = one["snapshots_in_service"].fillna(0)
            g = (one.assign(_b=one["avg_bikes"].fillna(0) * w, _w=w)
                    .groupby("hour_paris").agg(b=("_b", "sum"), w=("_w", "sum"), lo=("min_bikes", "min"), hi=("max_bikes", "max"))
                    .reset_index())
            g["avg"] = g["b"] / g["w"].where(g["w"] > 0)
            cap = stations.set_index("station_id").loc[pick, "capacity_observed"]
            st.caption("Nombre de vélos dans la station, heure par heure : la ligne est la moyenne, la zone claire va du "
                       "plus bas au plus haut observé.")
            fig = go.Figure()
            fig.add_scatter(x=g["hour_paris"], y=g["hi"], line=dict(width=0), showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=g["hour_paris"], y=g["lo"], fill="tonexty", fillcolor="rgba(15,139,141,.15)", line=dict(width=0),
                            name="Du plus bas au plus haut", hoverinfo="skip")
            fig.add_scatter(x=g["hour_paris"], y=g["avg"], name="Vélos (moyenne)", line=dict(color=ACCENT, width=3))
            if pd.notna(cap):
                fig.add_hline(y=cap, line_dash="dot", line_color=MUTED, annotation_text=f"nombre de bornes : {int(cap)}")
            fig.update_layout(xaxis_title="Heure de la journée", yaxis_title="Vélos dans la station", xaxis=dict(dtick=1))
            st.plotly_chart(style_fig(fig, 300), width="stretch")

# ================================================================ FIABILITÉ
with tab_fia:
    rate, n_missing_hours = reception_rate()
    frozen = unchanged[unchanged["looks_frozen_now"]]
    gaps = stations[stations["has_capacity_gap"]]
    rate_txt = dq.fmt_pct(rate) if pd.notna(rate) else "n/d"
    answer = (f"{rate_txt} des mesures attendues ont été reçues. {len(gaps)} station(s) ont un nombre de bornes annoncé "
              f"inexact, {len(bad_geo)} n'ont pas de position GPS valide, "
              + (f"{len(frozen)} sont à contrôler." if len(frozen) else "aucune n'est à contrôler."))
    banner("Peut-on se fier à ces chiffres ?", answer,
           "à savoir ce qui est solide et ce qui ne l'est pas avant de décider. Un trou dans les mesures ou un nombre "
           "de bornes faux déforment les résultats.")

    published = datetime.fromtimestamp(wh.stat().st_mtime)
    k1, k2, k3, k4 = st.columns(4)
    kpi(k1, "Jours de mesures", f"{n_days}", "Nombre de jours déjà enregistrés.")
    kpi(k2, "Mesures enregistrées", f"{int(meta['snapshots_rows']):,}".replace(",", " "), "Une mesure = l'état d'une station à une minute donnée.")
    kpi(k3, "Dernière mesure", last_snap.strftime("%d/%m %H:%M"), "Moment de la dernière mesure prise.", size=26)
    kpi(k4, "Base mise à jour le", published.strftime("%d/%m %H:%M"), "Le traitement de nuit (3 h) met la base à jour.", size=26)
    st.caption("Chaque nuit, avant de mettre la base à jour, des vérifications automatiques sont lancées. Si l'une échoue, "
               "rien n'est publié : ce que tu vois ici a donc passé les vérifications.")

    st.subheader("Les mesures sont-elles toutes arrivées ?")
    st.caption("Une mesure est prise chaque minute, donc 60 par heure. Vert : toutes reçues. Orange : il en manque. "
               "Case vide : aucune mesure, ou première / dernière heure de la période (incomplètes par nature).")
    cm = collection.copy()
    cm["val"] = cm["completeness"].where(~cm["is_partial_hour"])
    pv = cm.pivot(index="date_paris", columns="hour_paris", values="val").sort_index().reindex(columns=range(24))
    fig = go.Figure(go.Heatmap(z=pv.values, x=[f"{h} h" for h in pv.columns], y=[d.strftime("%d/%m") for d in pv.index],
                               zmin=0, zmax=1, colorscale=[[0, NO_BIKE], [0.9, "#BFE3D3"], [1, GOOD]], xgap=2, ygap=2,
                               colorbar=dict(title="Mesures reçues", tickformat=".0%"), hoverongaps=False,
                               hovertemplate="%{y} à %{x} : %{z:.0%} des mesures reçues<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style_fig(fig, 90 + 28 * len(pv)), width="stretch")
    incomplete = collection[(~collection["is_partial_hour"]) & (collection["completeness"] < 0.9)]
    if len(incomplete):
        inc = incomplete.sort_values(["date_paris", "hour_paris"]).assign(
            Jour=lambda d: d["date_paris"].map(lambda x: x.strftime("%d/%m/%Y")),
            Heure=lambda d: d["hour_paris"].astype(str) + " h",
            **{"Mesures reçues": lambda d: d["snapshots"].astype(str) + " sur 60",
               "Mesures manquantes": lambda d: d["missing_snapshots"].astype(str)})
        st.dataframe(inc[["Jour", "Heure", "Mesures reçues", "Mesures manquantes"]], hide_index=True, width="stretch")
    else:
        st.success("Aucune heure avec des mesures manquantes (hors première et dernière).")

    left, right = st.columns(2)
    with left:
        st.subheader("Nombre de bornes : annoncé ou observé ?")
        if gaps.empty:
            st.success("Le nombre de bornes annoncé correspond partout à ce qu'on observe.")
        else:
            st.dataframe(gaps[["name", "capacity_declared", "capacity_observed"]].rename(
                columns={"name": "Station", "capacity_declared": "Bornes annoncées", "capacity_observed": "Bornes observées"}),
                hide_index=True, width="stretch")
        st.caption("L'écart est le même à chaque mesure. Pour les calculs, on se fie donc au nombre de bornes observé.")
        st.subheader("Stations sans position GPS valide")
        if bad_geo.empty:
            st.success("Toutes les stations ont une position GPS valide.")
        else:
            st.dataframe(bad_geo[["station_id", "name", "lat", "lon"]].rename(
                columns={"station_id": "Numéro", "name": "Station", "lat": "Latitude", "lon": "Longitude"}),
                hide_index=True, width="stretch")
            st.caption("La source indique une position à zéro pour ces stations : elles ne sont pas sur la carte, "
                       "mais elles comptent dans tous les calculs.")
    with right:
        st.subheader("Stations dont le nombre de vélos ne change plus")
        u = unchanged.assign(Station=unchanged["station_id"].map(name_of)).sort_values("longest_unchanged_minutes", ascending=False).head(10)
        u = u.assign(**{"Plus longue période sans changement": u["longest_unchanged_minutes"].map(dq.fmt_minutes),
                        "En ce moment": u["current_unchanged_minutes"].map(dq.fmt_minutes),
                        "À faire contrôler ?": u["looks_frozen_now"].map({True: "Oui", False: "Non"})})
        st.dataframe(u[["Station", "Plus longue période sans changement", "En ce moment", "À faire contrôler ?"]],
                     hide_index=True, width="stretch")
        st.caption("Une station est signalée si son nombre de vélos et de places n'a pas bougé depuis plus de 6 heures. "
                   "C'est une alerte, pas une preuve de panne : une station peu utilisée peut rester immobile. "
                   "Ce délai sera ajusté quand on aura plus de jours de mesures.")

# ================================================================ À PROPOS
with tab_apr:
    banner("Qu'est-ce que MobilityFlow ?",
           "Un outil qui garde l'historique d'un réseau de vélos en libre-service, pour comprendre son fonctionnement.",
           "à aider un exploitant de vélos en libre-service à voir où rééquilibrer, quoi faire réparer, et à lui dire si ses chiffres sont fiables.")
    st.markdown("""
**Le problème.** Le service Bicloo indique seulement où sont les vélos *à cet instant*. Il ne garde aucun historique :
impossible de savoir quelles stations sont souvent sans vélo, à quelle heure, ou si l'une d'elles est bloquée.
MobilityFlow prend une **mesure chaque minute**, la conserve, la nettoie, la vérifie, puis la rend lisible ici.
""")
    st.graphviz_chart("""
digraph G {
  rankdir=LR; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fillcolor="white", color="#9AA9A7", fontname="Helvetica", fontsize=11];
  edge [color="#4B6A70"];
  api [label="Service Bicloo\\n(état des stations)"];
  raw [label="Mesures brutes\\n1 par minute"];
  subgraph cluster_night { label="Traitement automatique, chaque nuit à 3 h"; fontname="Helvetica"; fontsize=11; color="#0F8B8D"; style="rounded,dashed";
    pack [label="Mesures regroupées\\n1 fichier par jour"];
    check [label="Contrôle\\ndu fichier"];
    clean [label="Nettoyage"];
    calc [label="Calcul des\\nindicateurs"];
    test [label="Vérifications\\nautomatiques"];
    db [label="Base de\\ndonnées"];
  }
  app [label="Ce tableau\\nde bord", fillcolor="#E7F4F4"];
  api -> raw -> pack -> check -> clean -> calc -> test -> db -> app;
}""", width="stretch")

    st.subheader("Petit lexique")
    st.markdown("""
- **Mesure** : une « photo » de l'état de toutes les stations, prise chaque minute.
- **Station ouverte** : station en état de marche. Les pourcentages ne comptent que les minutes où elle est ouverte.
- **Borne** : emplacement où l'on accroche un vélo. Le nombre de bornes est la taille de la station.
- **Manque de vélos** : la station n'a aucun vélo pendant au moins **un cinquième du temps** (20 %).
- **Manque de places** : la station n'a aucune place libre pendant au moins un cinquième du temps.
- **Les deux** : la station manque de vélos *et* de places à des moments différents.
- **Bien équilibrée** : ni l'un ni l'autre. On y trouve en général un vélo et une place.
- **Bornes occupées** : part des bornes qui ont un vélo.
- **Station à contrôler** : son nombre de vélos n'a pas bougé depuis plus de 6 heures. À vérifier, sans certitude de panne.
""")
    st.subheader("Limites à connaître")
    st.markdown("""
- Pour l'instant, **peu de jours de mesures** : les classements sont indicatifs et se préciseront avec le temps.
- L'heure de dernier signalement fournie par le service est peu fiable : elle n'est pas utilisée.
- Quelques stations ont un nombre de bornes annoncé inexact (voir « Fiabilité des données »).
- La règle « un cinquième du temps » est un choix de lisibilité ; elle sera réexaminée avec plus de données.
- Les données vont jusqu'à la veille : ce n'est pas un outil en temps réel.
- Le traitement de nuit tourne en mode apprentissage sur un seul ordinateur, pas en production.
""")
    with st.expander("Sous le capot (pour les curieux)"):
        st.markdown("""
Python (collecte et conversion) · Parquet (fichiers compacts) · Airflow (planification de nuit) · Docker (environnement) ·
dbt (nettoyage et vérifications en SQL) · DuckDB (base de données) · Streamlit (cette page, en lecture seule).

**Données** : Bicloo, JCDecaux / Nantes Métropole, Licence Ouverte. Projet d'apprentissage en ingénierie de la donnée :
local, sans cloud, figé après quelques semaines de collecte.
""")