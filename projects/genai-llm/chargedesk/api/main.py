"""API ChargeDesk.

    uvicorn api.main:app --reload        # puis http://127.0.0.1:8000

GET  /          page de questions (questions types, soir courant, reponse et etapes)
GET  /health    etat
GET  /meta      soirs disponibles, questions proposees, lien ChargeTriage
GET  /evening/{soir}  liste du soir et bornes muettes hors liste (lu dans les donnees, sans LLM)
POST /ask       {"question": "...", "evening": "AAAA-MM-JJ"} -> reponse structuree + etapes
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from api.journal import Journal
from api.prepared import PreparedStore
from api.service import FIRST_EVENING, LAST_EVENING, DailyLimit, Desk, Unavailable, evening_overview
from api.templates import FREQUENT, POST_QUESTIONS, SITE_QUESTIONS
from chargedesk.data.snapshot import full_connection
from chargedesk.llm.client import QuotaExhausted, TransientError

PAGE = Path(__file__).with_name("page.html")
CHARGETRIAGE_URL = "https://chargetriage.onrender.com/liste"
CODE_URL = "https://github.com/soley000/omr-portfolio/tree/main/projects/genai-llm/chargedesk"
# Resultat officiel (jeu de test ouvert une fois le 20/10/2026, cadrage section 3 sexies)
EVAL_SUMMARY = "Évalué sur 62 questions figées : 95 % de réponses justes au test, aucun chiffre inventé"


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    evening: date = Field(description="Soir courant simule (2021-08-31 a 2021-12-30)")

    @field_validator("evening")
    @classmethod
    def in_replay(cls, v: date) -> date:
        if not FIRST_EVENING <= v <= LAST_EVENING:
            raise ValueError(f"le soir doit etre entre {FIRST_EVENING} et {LAST_EVENING} (periode du rejeu)")
        return v


def create_app(desk: Desk | None = None, journal: Journal | None = None) -> FastAPI:
    app = FastAPI(title="ChargeDesk", version="0.8.0")
    if desk is None:
        from chargedesk.config import load_config, warehouse_path
        import os
        from chargedesk.config import data_dir
        cfg = load_config()
        prepared = os.environ.get("CHARGEDESK_PREPARED") or data_dir(cfg) / "demo" / "prepared.json"
        desk = Desk(warehouse_path(cfg), prepared=PreparedStore(prepared))
        if journal is None:
            journal = Journal(os.environ.get("CHARGEDESK_JOURNAL") or data_dir(cfg) / "monitoring" / "questions.jsonl")
    journal = journal or Journal(None)
    app.state.desk = desk

    @app.get("/health")
    def health():
        return {"status": "ok", "champion": desk.champion, "fallback": desk.fallback}

    @app.get("/meta")
    def meta():
        con = full_connection(desk.warehouse)
        try:
            d0, d1 = con.execute("select min(day), max(day) from marts.fct_post_day").fetchone()
            n_posts = con.execute("select count(*) from marts.dim_post").fetchone()[0]
            n_sites = con.execute("select count(*) from marts.dim_site").fetchone()[0]
        finally:
            con.close()
        return {"first_evening": FIRST_EVENING, "last_evening": LAST_EVENING, "chargetriage_url": CHARGETRIAGE_URL,
                "code_url": CODE_URL, "eval_summary": EVAL_SUMMARY,
                "coverage": {"data_start": d0, "data_end": d1, "n_posts": n_posts, "n_sites": n_sites,
                             "place": "Jiaxing (Chine)"},
                "prepared_evenings": desk.prepared.evenings(),
                "post_questions": POST_QUESTIONS, "site_questions": SITE_QUESTIONS, "frequent": FREQUENT}

    @app.get("/evening/{evening}")
    def evening_view(evening: date):
        if not FIRST_EVENING <= evening <= LAST_EVENING:
            raise HTTPException(422, f"le soir doit etre entre {FIRST_EVENING} et {LAST_EVENING}")
        return evening_overview(desk.warehouse, evening)

    @app.post("/ask")
    def ask(req: AskRequest):
        t0 = time.monotonic()
        base = {"evening": req.evening, "question": req.question[:300]}
        try:
            out = desk.ask(req.question, req.evening)
        except DailyLimit as exc:
            journal.record({**base, "source": "refusee", "http": 429, "error": str(exc)[:300],
                            "latency_s": round(time.monotonic() - t0, 2)})
            raise HTTPException(429, str(exc)) from exc
        except (Unavailable, QuotaExhausted, TransientError) as exc:
            msg = str(exc) if isinstance(exc, Unavailable) else ("Le service de langage est indisponible pour le "
                                                                  "moment. Réessayez dans quelques minutes.")
            journal.record({**base, "source": "direct", "http": 503, "error": str(exc)[:300],
                            "latency_s": round(time.monotonic() - t0, 2)})
            raise HTTPException(503, msg) from exc
        except Exception as exc:                            # bug : on le trace, puis 500
            journal.record({**base, "source": "direct", "http": 500, "error": f"{type(exc).__name__}: {exc}"[:300],
                            "latency_s": round(time.monotonic() - t0, 2)})
            raise
        a = out.get("answer") or {}
        journal.record({**base, "source": "preparee" if out.get("prepared") else "direct", "http": 200,
                        "status": a.get("status"), "model": out.get("model"),
                        "fallback_used": out.get("fallback_used"), "notes": out.get("notes"),
                        "latency_s": round(time.monotonic() - t0, 2), "llm_calls": out.get("llm_calls"),
                        "llm_latencies_s": out.get("llm_latencies_s"), "tokens": out.get("tokens", 0),
                        "cached_calls": out.get("cached_calls", 0),
                        "tools": [s["tool"] for s in out.get("steps", [])],
                        "n_figures": len(a.get("figures") or [])})
        return out

    @app.get("/stats")
    def stats():
        """Compteurs agreges depuis le demarrage (aucune question, aucune donnee individuelle)."""
        return journal.stats()

    @app.get("/", response_class=HTMLResponse)
    def page():
        return PAGE.read_text(encoding="utf-8")

    return app


def __getattr__(name):          # `app` cree a la demande : importer le module ne demande pas de cle
    if name == "app":
        return create_app()
    raise AttributeError(name)
