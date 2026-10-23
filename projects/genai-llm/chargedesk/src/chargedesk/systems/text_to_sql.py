"""Reference 2 : text-to-SQL libre (approche naive).

1. Le LLM recoit les regles et le schema de l'entrepot (avec la documentation
   dbt) et ecrit une requete SQL, ou demande une precision, ou refuse.
2. La requete passe le garde-fou SQL et s'execute dans la vue "soir courant"
   (lecture seule). En cas d'erreur, le LLM a UNE chance de la corriger.
3. Le LLM redige la reponse a partir des lignes obtenues.
Les lignes renvoyees par la requete servent a verifier que les chiffres sont etayes.
"""
from __future__ import annotations

import json

from chargedesk.data.snapshot import snapshot_connection
from chargedesk.guards.sql import SQLRejected, run_checked
from chargedesk.systems.common import (ANSWER_FORMAT, RULES, extract_json, parse_answer,
                                       question_message, schema_description)

NAME = "text_to_sql"
MAX_SQL_ATTEMPTS = 2

STEP1 = """Tu disposes d'une base DuckDB (lecture seule). N'utilise que ces tables, toujours prefixees par marts. :

{schema}

Reponds UNIQUEMENT par un objet JSON, sans texte autour, de l'une de ces formes :
{{"action": "sql", "sql": "une seule requete SELECT DuckDB"}}
{{"action": "clarify", "text": "la precision a demander"}}
{{"action": "refuse", "refusal_reason": "causal" | "future" | "out_of_data" | "modification", "text": "pourquoi"}}
Les dates s'ecrivent date 'AAAA-MM-JJ'. La requete doit renvoyer directement les chiffres utiles."""


def run(llm, warehouse, evening, question: str, rep: int = 0) -> dict:
    con = snapshot_connection(warehouse, evening)
    out = {"calls": [], "tool_results": [], "sql": [], "sql_errors": []}
    try:
        system = RULES + "\n\n" + STEP1.format(schema=schema_description(con))
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": question_message(evening, question)}]
        rows = None
        for attempt in range(MAX_SQL_ATTEMPTS):
            r = llm.chat(messages, rep=rep)
            out["calls"].append(r.__dict__)
            try:
                step = extract_json(r.content)
            except ValueError as exc:
                out["answer"], out["error"] = None, f"etape 1 illisible : {exc}"
                return out
            action = step.get("action")
            if action in ("clarify", "refuse"):
                try:
                    from chargedesk.eval.schema import Answer
                    ans = Answer(status=action, text=step.get("text") or "-",
                                 refusal_reason=step.get("refusal_reason") if action == "refuse" else None)
                    out["answer"] = ans.model_dump(mode="json")
                except Exception as exc:
                    out["answer"], out["error"] = None, f"reponse invalide : {exc}"
                return out
            sql = step.get("sql") or ""
            out["sql"].append(sql)
            try:
                rows = run_checked(con, sql)
                break
            except (SQLRejected, Exception) as exc:
                out["sql_errors"].append(str(exc)[:300])
                messages = messages + [
                    {"role": "assistant", "content": r.content},
                    {"role": "user", "content": f"Erreur : {str(exc)[:300]}\nCorrige la requete (meme format JSON)."},
                ]
        if rows is None:
            out["answer"], out["error"] = None, "aucune requete valide"
            return out
        out["tool_results"].append(rows)
        final = [
            {"role": "system", "content": RULES + "\n\n" + ANSWER_FORMAT},
            {"role": "user", "content": question_message(evening, question)
             + f"\n\nRequete executee :\n{out['sql'][-1]}\n\nResultat (JSON) :\n"
             + json.dumps(rows[:50], ensure_ascii=False, default=str)
             + "\n\nSources a citer : [\"run_sql\"]."},
        ]
        r = llm.chat(final, rep=rep)
        out["calls"].append(r.__dict__)
        try:
            out["answer"] = parse_answer(r.content).model_dump(mode="json")
        except ValueError as exc:
            out["answer"], out["error"] = None, str(exc)
        return out
    finally:
        con.close()
