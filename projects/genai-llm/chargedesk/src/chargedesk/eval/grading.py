"""Correction automatique d'une reponse de ChargeDesk.

Une reponse est juste si son statut est le bon, si la raison du refus est
la bonne, et si tous les chiffres attendus sont presents dans la tolerance
de leur unite. Un chiffre est etaye s'il se retrouve dans un resultat
d'outil : le LLM ne doit jamais calculer ni inventer un nombre.
"""
from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from chargedesk.eval.schema import Answer, Expected, Figure

DEFAULT_TOLERANCES = {
    "count": {"abs": 0},
    "rate": {"abs": 0.001},
    "score": {"abs": 0.005},
    "kwh": {"rel": 0.005},
    "days": {"abs": 0},
}


def close(a: float, b: float, unit: str, tolerances: dict | None = None) -> bool:
    tol = (tolerances or DEFAULT_TOLERANCES)[unit]
    if "rel" in tol:
        return math.isclose(a, b, rel_tol=tol["rel"], abs_tol=1e-9)
    return abs(a - b) <= tol["abs"] + 1e-9


def figure_matches(expected: Figure, got: Figure, tolerances: dict | None = None) -> bool:
    return expected.unit == got.unit and close(expected.value, got.value, expected.unit, tolerances)


def numbers_in(obj: Any) -> list[float]:
    """Tous les nombres d'un resultat d'outil (dictionnaires et listes compris)."""
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [] if isinstance(obj, float) and math.isnan(obj) else [float(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in numbers_in(v)]
    if isinstance(obj, (list, tuple)):
        return [n for v in obj for n in numbers_in(v)]
    return []


class Grade(BaseModel):
    status_ok: bool
    reason_ok: bool
    figures_ok: bool
    unsupported: list[str]
    correct: bool


def grade(answer: Answer, expected: Expected, tool_results: list[Any],
          tolerances: dict | None = None) -> Grade:
    status_ok = answer.status == expected.status
    reason_ok = answer.refusal_reason == expected.refusal_reason
    figures_ok = all(
        any(figure_matches(e, g, tolerances) for g in answer.figures)
        for e in expected.figures
    )
    pool = [n for r in tool_results for n in numbers_in(r)]
    unsupported = [
        f.name for f in answer.figures
        if not any(close(f.value, n, f.unit, tolerances) for n in pool)
    ]
    return Grade(
        status_ok=status_ok,
        reason_ok=reason_ok,
        figures_ok=figures_ok,
        unsupported=unsupported,
        correct=status_ok and reason_ok and figures_ok,
    )