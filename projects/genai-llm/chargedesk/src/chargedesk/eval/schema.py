"""Format des reponses de ChargeDesk et des reponses attendues.

Le LLM ne rend pas un texte libre : il remplit Answer, qui est controle
par Pydantic. Expected decrit la reponse attendue d'une question du jeu
d'evaluation (phase 3).
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Status = Literal["answered", "clarify", "refuse"]
Unit = Literal["count", "rate", "score", "kwh", "days"]
RefusalReason = Literal["causal", "future", "out_of_data", "modification"]


class Figure(BaseModel):
    """Un chiffre de la reponse."""
    name: str = Field(description="Ce que mesure le chiffre, ex. 'pannes Shopping Mall'.")
    value: float
    unit: Unit


class Answer(BaseModel):
    """Reponse rendue par l'agent."""
    status: Status
    text: str = Field(min_length=1, description="Reponse pour l'exploitant, en francais.")
    figures: list[Figure] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    sources: list[str] = Field(default_factory=list, description="Outils ou tables utilises.")
    refusal_reason: RefusalReason | None = None

    @model_validator(mode="after")
    def coherent(self) -> "Answer":
        if self.status == "refuse" and self.refusal_reason is None:
            raise ValueError("un refus doit donner sa raison")
        if self.status != "refuse" and self.refusal_reason is not None:
            raise ValueError("refusal_reason seulement pour un refus")
        if self.figures and not self.sources:
            raise ValueError("une reponse chiffree doit citer au moins une source")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("la periode doit commencer avant de finir")
        return self


class Expected(BaseModel):
    """Reponse attendue pour une question du jeu d'evaluation."""
    status: Status
    figures: list[Figure] = Field(default_factory=list)
    refusal_reason: RefusalReason | None = None