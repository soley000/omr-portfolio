"""Reference 1 : le LLM seul, sans aucun acces aux donnees (plancher).

Il connait les regles et le format de reponse, mais aucun chiffre. Le bareme
doit montrer qu'il invente les chiffres (non etayes) et voir s'il sait refuser.
"""
from __future__ import annotations

from chargedesk.systems.common import ANSWER_FORMAT, RULES, parse_answer, question_message

NAME = "no_tools"


def run(llm, warehouse, evening, question: str, rep: int = 0) -> dict:
    messages = [
        {"role": "system", "content": RULES + "\n\nTu n'as AUCUN acces aux donnees.\n\n" + ANSWER_FORMAT},
        {"role": "user", "content": question_message(evening, question)},
    ]
    r = llm.chat(messages, rep=rep)
    out = {"calls": [r.__dict__], "tool_results": [], "sql": [], "sql_errors": []}
    try:
        out["answer"] = parse_answer(r.content).model_dump(mode="json")
    except ValueError as exc:
        out["answer"], out["error"] = None, str(exc)
    return out
