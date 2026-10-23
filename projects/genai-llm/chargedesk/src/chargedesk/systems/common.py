"""Elements communs aux systemes evalues : regles, format de reponse, lecture du JSON."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from chargedesk.config import PROJECT_ROOT
from chargedesk.eval.schema import Answer

MARTS_DOC = PROJECT_ROOT / "dbt" / "models" / "marts" / "_marts.yml"

RULES = """Tu es ChargeDesk, l'assistant d'un exploitant de 92 bornes de recharge reparties sur 13 sites
(donnees de Jiaxing, Chine, du 1er janvier 2020 au 31 decembre 2021).
Chaque soir, un modele (ChargeTriage) classe les bornes par risque d'episode de pannes le lendemain.

Regles :
- Nous sommes le SOIR COURANT indique. Rien apres ce soir n'est connu.
- "les 7 derniers jours" = le soir courant inclus et les 6 jours precedents ; idem pour 28 jours.
- "ce mois-ci" / "depuis le debut du mois" = du 1er du mois au soir courant.
- "la liste" = le top 10 du modele champion ce soir-la ; "la regle simple" = le top 10 du modele fallback.
- "muette" / "a l'arret" = aucune recharge sur les 7 derniers jours.
- "fiabilite de la liste" = part des bornes listees ayant eu un episode le lendemain,
  sur les listes des 28 soirs precedents dont le resultat est connu.
- Ne donne jamais un chiffre que tu n'as pas obtenu des donnees.
- Si la question est ambigue (quelle borne ? quel site ? nombre ou taux ? quelle periode ?), demande une precision.
- Refuse si la question demande une cause (les donnees ne contiennent ni interventions ni contexte),
  une prevision au-dela du lendemain, une information absente des donnees (couts, techniciens...),
  ou une modification des donnees."""

ANSWER_FORMAT = """Reponds UNIQUEMENT par un objet JSON de cette forme, sans texte autour :
{
  "status": "answered" | "clarify" | "refuse",
  "text": "reponse en francais pour l'exploitant",
  "figures": [{"name": "ce que mesure le chiffre", "value": 123, "unit": "count" | "rate" | "score" | "kwh" | "days"}],
  "period_start": "AAAA-MM-JJ" ou null,
  "period_end": "AAAA-MM-JJ" ou null,
  "sources": ["outils ou tables utilises"],
  "refusal_reason": null | "causal" | "future" | "out_of_data" | "modification"
}
Unites : count = nombre (pannes, recharges, bornes, rang, numero de borne), rate = taux entre 0 et 1
(jamais en pourcentage), score = score du modele entre 0 et 1, kwh = energie, days = nombre de jours.
Pour "clarify" et "refuse", laisse figures vide. Pour "refuse", refusal_reason est obligatoire."""


def question_message(evening: date, question: str) -> str:
    return f"Soir courant : {evening.isoformat()}\nQuestion : {question}"


def extract_json(text: str | None) -> dict:
    """Premier objet JSON valide d'une reponse (accepte un bloc ```json et du texte apres l'objet)."""
    if not text:
        raise ValueError("reponse vide")
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = [m.group(1)] if m else []
    candidates += [text[i:] for i, ch in enumerate(text) if ch == "{"][:20]
    decoder = json.JSONDecoder()
    for c in candidates:
        try:
            obj, _ = decoder.raw_decode(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("aucun objet JSON lisible dans la reponse")


def parse_answer(text: str | None) -> Answer:
    """JSON du LLM -> Answer controle par Pydantic. Leve ValueError si invalide."""
    try:
        return Answer(**extract_json(text))
    except (ValueError, ValidationError, TypeError) as exc:
        raise ValueError(f"reponse invalide : {str(exc)[:300]}") from exc


def schema_description(con) -> str:
    """Tables autorisees, colonnes et types (vue soir courant) + descriptions de la documentation dbt."""
    docs = {}
    if MARTS_DOC.exists():
        y = yaml.safe_load(MARTS_DOC.read_text(encoding="utf-8"))
        for m in y.get("models", []):
            docs[m["name"]] = (m.get("description", ""),
                               {c["name"]: c.get("description", "") for c in m.get("columns", [])})
    from chargedesk.guards.sql import ALLOWED_TABLES
    lines = []
    for table in sorted(ALLOWED_TABLES):
        cols = con.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = 'marts' and table_name = ? and table_catalog = current_database() "
            "order by ordinal_position", [table]).fetchall()
        if not cols:
            continue
        desc, cdocs = docs.get(table, ("", {}))
        lines.append(f"marts.{table} : {desc}")
        for c, t in cols:
            extra = f" -- {cdocs[c]}" if cdocs.get(c) else ""
            lines.append(f"  - {c} ({t}){extra}")
    return "\n".join(lines)
