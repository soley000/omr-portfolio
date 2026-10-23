"""Le service derriere l'API : l'agent avec son LLM champion, et la bascule vers le repli.

Le champion (le plus juste en evaluation) a un BUDGET DE TEMPS : s'il ne termine pas a temps
(offre gratuite saturee), la question repart sur le repli, plus rapide. La page l'indique.
Le LLM est fabrique par `llm_factory(nom)` : en production, LLMClient.from_config ; dans les tests,
un faux LLM (aucune cle, aucun appel reseau).
"""
from __future__ import annotations

import threading
import time
from datetime import date
from pathlib import Path
from typing import Callable

from api.prepared import PreparedStore
from chargedesk.data.snapshot import snapshot_connection
from chargedesk.llm.client import LLMClient, QuotaExhausted, TransientError
from chargedesk.systems import agent
from chargedesk.tools.registry import call_tool

FIRST_EVENING, LAST_EVENING = date(2021, 8, 31), date(2021, 12, 30)   # soirs du rejeu ChargeTriage

# Patience de l'API (l'evaluation, elle, attend plus longtemps et relance davantage)
API_PATIENCE = {"flash_lite": {"timeout_s": 30, "max_retries": 2, "max_timeouts": 0, "max_wait_s": 6},
                "gpt_oss": {"timeout_s": 30, "max_retries": 2, "max_timeouts": 0, "max_wait_s": 6}}


EXHAUSTED_PAUSE_S = 3600     # un modele a court de quota est mis de cote une heure, puis reessaye


def default_factory(name: str):
    return LLMClient.from_config(name, **API_PATIENCE.get(name, {}))


def evening_overview(warehouse, evening: date) -> dict:
    """Liste du soir, bornes muettes hors liste et fiabilite recente : lu dans les donnees, sans LLM.
    Memes outils que l'agent, donc memes definitions et meme regle du soir courant."""
    con = snapshot_connection(warehouse, evening)
    try:
        _, lst = call_tool(con, evening, "get_evening_list", {})
        _, status = call_tool(con, evening, "get_post_status", {})
        _, rel = call_tool(con, evening, "get_list_reliability", {})
    finally:
        con.close()
    listed = {r["post_id"] for r in lst.get("list", [])}
    sites: dict = {}
    for p in status.get("posts", []):
        if p["silent"] and p["post_id"] not in listed:
            s = sites.setdefault(p["site"], {"site": p["site"], "posts": [], "max_days": 0})
            s["posts"].append(p["post_id"])
            s["max_days"] = max(s["max_days"], p["days_without_recharge"] or 0)
    return {"evening": evening, "list": lst.get("list", []),
            "reliability": {m: (rel.get(m) or {}).get("reliability") for m in ("champion", "fallback")},
            "reliability_evenings": rel.get("evenings"),
            "silent_sites": sorted(sites.values(), key=lambda s: -len(s["posts"]))}


class DailyLimit(Exception):
    pass


class Unavailable(Exception):
    """Aucun LLM ne peut repondre maintenant (message destine a l'exploitant)."""


class _Budgeted:
    """Enveloppe un LLM : refuse un nouvel appel une fois le budget de la question depasse."""
    def __init__(self, llm, budget_s: float):
        self.llm, self.budget_s, self.t0 = llm, budget_s, time.monotonic()

    def chat(self, *a, **k):
        left = self.budget_s - (time.monotonic() - self.t0)
        if left <= 0:
            raise TransientError(f"trop lent : budget de {self.budget_s:.0f} s depasse")
        if isinstance(self.llm, LLMClient):          # l'appel en cours est coupe a la fin du budget
            k["timeout"] = max(1.0, left)
        return self.llm.chat(*a, **k)


class Desk:
    def __init__(self, warehouse: Path | str, llm_factory: Callable = default_factory,
                 champion: str = "flash_lite", fallback: str | None = "gpt_oss",
                 max_questions_per_day: int = 50, champion_budget_s: float = 20,
                 prepared: PreparedStore | None = None):
        self.warehouse, self.llm_factory = warehouse, llm_factory
        self.champion, self.fallback = champion, fallback
        self.max_per_day, self.budget_s = max_questions_per_day, champion_budget_s
        self._llms: dict = {}
        self._day, self._count = date.today(), 0
        self._exhausted: dict[str, float] = {}     # modele -> moment ou son quota a ete epuise
        self.prepared = prepared or PreparedStore(None)
        self._lock = threading.Lock()

    def _llm(self, name: str):
        if name not in self._llms:
            self._llms[name] = self.llm_factory(name)
        return self._llms[name]

    def _take_quota(self) -> None:
        with self._lock:
            if date.today() != self._day:
                self._day, self._count = date.today(), 0
            if self._count >= self.max_per_day:
                raise DailyLimit(f"limite de la démo atteinte ({self.max_per_day} questions par jour)")
            self._count += 1

    def _available(self, name: str | None) -> bool:
        return bool(name) and time.monotonic() - self._exhausted.get(name, -1e9) > EXHAUSTED_PAUSE_S

    def ask(self, question: str, evening: date) -> dict:
        rec = self.prepared.get(evening, question)
        if rec:                                    # reponse preparee : instantanee, hors quota
            return {"answer": rec["answer"], "steps": rec.get("steps", []), "model": rec.get("model"),
                    "fallback_used": False, "notes": [], "llm_calls": rec.get("llm_calls", 0),
                    "llm_latencies_s": [], "latency_s": 0.0,
                    "prepared": True, "prepared_at": rec.get("prepared_at")}
        self._take_quota()
        t0 = time.monotonic()
        notes: list[str] = []
        chain = [m for m in (self.champion, self.fallback) if self._available(m)]
        if not chain:
            raise Unavailable("Les deux modèles gratuits sont à court de quota pour le moment. "
                              "Réessayez plus tard, ou choisissez un soir aux réponses préparées.")
        out, used = None, None
        for i, name in enumerate(chain):
            has_next = i + 1 < len(chain)
            try:
                llm = self._llm(name)
            except RuntimeError:                   # cle API absente (ex. secret non saisi sur l'hebergeur)
                notes.append(f"{name} : clé API absente")
                if not has_next:
                    raise Unavailable("Aucun modèle de langage n'est configuré sur ce serveur. "
                                      "Les soirs aux réponses préparées restent disponibles.")
                continue
            if has_next and name == self.champion:   # budget de temps seulement s'il existe un repli
                llm = _Budgeted(llm, self.budget_s)
            try:
                out, used = agent.run(llm, self.warehouse, evening, question), name
                break
            except QuotaExhausted:
                self._exhausted[name] = time.monotonic()
                notes.append(f"{name} : quota épuisé")
            except TransientError as exc:
                msg = str(exc)
                notes.append(f"{name} : " + ("connexion impossible" if "connexion" in msg
                                             else "trop lent" if "lent" in msg or "delai" in msg
                                             else "occupé"))
            if not has_next:
                raise Unavailable("Le service de langage gratuit ne répond pas pour le moment. Réessayez dans "
                                  "quelques minutes, ou choisissez un soir aux réponses préparées. ("
                                  + " ; ".join(notes) + ")")
        steps = [{"tool": t["tool"], "ok": t["ok"],
                  "detail": (t["result"].get("error") if not t["ok"] else None)}
                 for t in out.get("tool_trace", [])]
        calls = out.get("calls", [])
        return {"answer": out.get("answer"), "steps": steps, "model": used,
                "fallback_used": used != self.champion, "notes": notes,
                "llm_calls": len(calls), "llm_latencies_s": [round(c["latency_s"], 1) for c in calls],
                "tokens": sum((c.get("prompt_tokens") or 0) + (c.get("completion_tokens") or 0) for c in calls),
                "cached_calls": sum(1 for c in calls if c.get("cached")),
                "prepared": False,
                "latency_s": round(time.monotonic() - t0, 2)}
