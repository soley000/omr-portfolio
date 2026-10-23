"""Lecture et controle du jeu de questions (eval/questions.yaml)."""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from chargedesk.config import PROJECT_ROOT
from chargedesk.eval.schema import RefusalReason, Status, Unit

QUESTIONS_PATH = PROJECT_ROOT / "eval" / "questions.yaml"

Category = Literal[
    "fact", "comparison", "list", "alert", "reliability",
    "ambiguous", "causal", "future", "out_of_data", "modification",
]


class FigureSpec(BaseModel):
    name: str
    unit: Unit
    sql: str


class Question(BaseModel):
    id: str
    split: Literal["dev", "test"]
    evening: date
    category: Category
    question: str = Field(min_length=5)
    expected_status: Status
    refusal_reason: RefusalReason | None = None
    figures: list[FigureSpec] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def coherent(self) -> "Question":
        if self.expected_status == "answered" and not self.figures:
            raise ValueError(f"{self.id} : une question 'answered' doit avoir des chiffres attendus")
        if self.expected_status != "answered" and self.figures:
            raise ValueError(f"{self.id} : seules les questions 'answered' ont des chiffres")
        if (self.expected_status == "refuse") != (self.refusal_reason is not None):
            raise ValueError(f"{self.id} : refusal_reason obligatoire pour un refus, et seulement pour un refus")
        if not self.id.startswith(f"{self.split}-"):
            raise ValueError(f"{self.id} : l'identifiant doit commencer par '{self.split}-'")
        return self


def load_questions(path: Path | None = None) -> list[Question]:
    with open(path or QUESTIONS_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    questions = [Question(**q) for q in raw["questions"]]
    dupes = [k for k, n in Counter(q.id for q in questions).items() if n > 1]
    if dupes:
        raise ValueError(f"identifiants en double : {dupes}")
    return questions


def check_plan(questions: list[Question], plan: dict) -> list[str]:
    """Verifie le decoupage et la repartition prevus dans config.yaml. Renvoie les ecarts."""
    problems = []
    for split, spec in plan["splits"].items():
        start, end = date.fromisoformat(str(spec["start"])), date.fromisoformat(str(spec["end"]))
        qs = [q for q in questions if q.split == split]
        for q in qs:
            if not start <= q.evening <= end:
                problems.append(f"{q.id} : soir {q.evening} hors de la periode {split} ({start} a {end})")
        counts = Counter(q.category for q in qs)
        for cat, n in plan["per_split"].items():
            if counts.get(cat, 0) != n:
                problems.append(f"{split} / {cat} : {counts.get(cat, 0)} questions, {n} prevues")
    return problems
