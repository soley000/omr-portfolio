"""Reponses preparees a l'avance par l'agent, pour les questions que la page propose sur quelques soirs.

Ce sont de vraies reponses de l'agent (memes outils, meme LLM champion), calculees une fois quand le
fournisseur gratuit est disponible, puis servies instantanement par l'API. Le fichier vit dans le dossier
de donnees (jamais dans Git) et sera copie dans l'image Docker.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

# Soirs choisis pour montrer des situations differentes (cadrage, phases 1 et 3)
SHOWCASE = [
    date(2021, 9, 15),    # soir ordinaire, debut du rejeu
    date(2021, 10, 5),    # Technology Park muet, absent de la liste
    date(2021, 10, 15),   # liste nettement plus fiable que la regle simple
    date(2021, 11, 10),   # soir ordinaire
    date(2021, 11, 28),   # liste a peine meilleure que la regle simple
    date(2021, 12, 8),    # soir ordinaire
    date(2021, 12, 21),   # Tourist Attraction a l'arret
    date(2021, 12, 30),   # Tourist Attraction : reprise partielle
]


def norm(question: str) -> str:
    return re.sub(r"[\s?!.]+$", "", re.sub(r"\s+", " ", question.strip().lower()))


def key(evening: date | str, question: str) -> str:
    return f"{evening}|{norm(question)}"


class PreparedStore:
    def __init__(self, path: Path | str | None):
        self.path = Path(path) if path else None
        self.items: dict = {}
        if self.path and self.path.exists():
            self.items = json.loads(self.path.read_text(encoding="utf-8")).get("items", {})

    def get(self, evening: date, question: str) -> dict | None:
        return self.items.get(key(evening, question))

    def put(self, evening: date, question: str, record: dict) -> None:
        self.items[key(evening, question)] = {"evening": str(evening), "question": question, **record}

    def evenings(self) -> list[str]:
        return sorted({v["evening"] for v in self.items.values()})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "items": self.items}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(self.path)
