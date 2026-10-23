"""ChargeDesk : l'agent.

Le LLM recoit la question, le soir courant et une boite a outils (tools/registry.py).
A chaque tour, il appelle un ou plusieurs outils, lit leurs resultats et decide de la
suite ; quand il a ce qu'il faut, il repond au format JSON (Answer). Tous les outils
lisent la vue "soir courant" : l'agent ne peut pas voir le futur.
Garde-fous : au plus MAX_STEPS tours d'outils, arguments controles par Pydantic,
SQL libre seulement en dernier recours et filtre, reponse finale controlee par Pydantic.
"""
from __future__ import annotations

import json
import time

from chargedesk.data.snapshot import snapshot_connection
from chargedesk.llm.client import ToolCallRejected
from chargedesk.systems.common import ANSWER_FORMAT, RULES, parse_answer, question_message
from chargedesk.tools.registry import call_tool, tool_specs

NAME = "agent"
MAX_STEPS = 6

GUIDE = """Tu disposes d'outils qui lisent les donnees telles qu'elles etaient connues au soir courant.
Methode :
- Tout chiffre de ta reponse doit venir d'un resultat d'outil, recopie tel quel. Ne calcule rien toi-meme :
  pour un ecart entre deux periodes, utilise compare_periods ; pour un nombre de bornes, utilise l'outil qui le compte.
- Utilise les periodes nommees (last_7_days, month_to_date, previous_month...) ; years_back=1 pour l'an dernier.
- "Pourquoi telle borne est dans la liste / en tete" = expliquer son SCORE avec get_post_signals : c'est autorise.
  Seule la CAUSE des pannes est hors de portee des donnees.
- "Fonctionne encore", "a l'arret", "muette", "depuis combien de jours sans recharge" = etat actuel : get_post_status
  (les alertes de get_silent_alerts disent quand une alerte a ete levee, pas l'etat actuel).
  Pour tout le reseau, appelle get_post_status sans argument : un seul appel donne le nombre et la liste.
- "La liste est-elle fiable" = get_list_reliability ; resultat d'une liste passee (combien et lesquelles) = get_list_hits.
- "Quelles bornes ont le plus de pannes / le plus fort taux..." = rank_posts (classement), pas run_sql.
- run_sql seulement si aucun autre outil ne convient.
- AVANT tout appel d'outil, verifie que la question designe un indicateur precis. Des mots comme
  "problematique", "a problemes", "le pire", "qui va mal", "le plus touche", sans dire s'il s'agit du nombre
  de pannes, du taux de pannes, du score du modele ou des recharges, rendent la question ambigue :
  reponds status "clarify" en proposant ces choix, sans appeler d'outil et sans choisir a la place de l'exploitant.
- Si la question demande une cause, l'avenir, une donnee absente ou une modification :
  reponds directement (refuse) sans appeler d'outil.
Quand tu as les chiffres, reponds. Sources : les noms des outils utilises."""


def _assistant_message(r) -> dict:
    calls = r.raw_tool_calls or [{"id": c["id"], "type": "function",
                                  "function": {"name": c["name"], "arguments": c["arguments"]}}
                                 for c in r.tool_calls]
    return {"role": "assistant", "content": r.content, "tool_calls": calls}


def _rejection_feedback(msg: str) -> str:
    if "attempted to call tool" in msg:
        return ("Erreur : tu as appele un outil qui n'existe pas. Pour donner ta reponse finale, "
                "ecris l'objet JSON directement dans ton message, sans appeler d'outil.")
    return (f"Erreur dans ton appel d'outil : {msg[:300]}. Corrige les arguments "
            "(omets un champ optionnel plutot que de lui donner la valeur null).")


def run(llm, warehouse, evening, question: str, rep: int = 0) -> dict:
    con = snapshot_connection(warehouse, evening)
    out = {"calls": [], "tool_results": [], "tool_trace": [], "sql": [], "sql_errors": [],
           "tool_time_s": 0.0}
    tools = tool_specs()
    messages = [{"role": "system", "content": RULES + "\n\n" + GUIDE + "\n\n" + ANSWER_FORMAT},
                {"role": "user", "content": question_message(evening, question)}]
    try:
        for step in range(MAX_STEPS + 1):
            last = step == MAX_STEPS
            if last:
                messages.append({"role": "user", "content": "Nombre maximal d'appels atteint : "
                                 "reponds maintenant au format JSON avec ce que tu as."})
            try:
                r = llm.chat(messages, tools=None if last else tools, rep=rep)
            except ToolCallRejected as exc:   # refuse par le fournisseur : on le dit au modele
                out["calls"].append({"latency_s": exc.latency_s, "prompt_tokens": 0, "completion_tokens": 0,
                                     "tool_calls": [], "cached": False})
                out["tool_trace"].append({"step": step, "tool": "(rejete par le fournisseur)",
                                          "arguments": None, "ok": False, "result": {"error": str(exc)[:300]}})
                out["provider_rejections"] = out.get("provider_rejections", 0) + 1
                messages.append({"role": "user", "content": _rejection_feedback(str(exc))})
                continue
            out["calls"].append(r.__dict__)
            if r.tool_calls and not last:
                messages.append(_assistant_message(r))
                for c in r.tool_calls:
                    t0 = time.monotonic()
                    ok, result = call_tool(con, evening, c["name"], c["arguments"])
                    out["tool_time_s"] += time.monotonic() - t0
                    out["tool_trace"].append({"step": step, "tool": c["name"], "arguments": c["arguments"],
                                              "ok": ok, "result": result})
                    if ok:
                        out["tool_results"].append(result)
                    if c["name"] == "run_sql":
                        q = (json.loads(c["arguments"] or "{}") if isinstance(c["arguments"], str)
                             else c["arguments"]).get("query", "")
                        out["sql"].append(q)
                        if not ok:
                            out["sql_errors"].append(result["error"])
                    messages.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": json.dumps(result, ensure_ascii=False, default=str)})
                continue
            try:
                out["answer"] = parse_answer(r.content).model_dump(mode="json")
            except ValueError as exc:
                if last or "retried_format" in out:
                    # secours honnete plutot qu'une reponse vide : on demande de reformuler
                    out["answer"] = {"status": "clarify", "figures": [], "sources": [], "refusal_reason": None,
                                     "period_start": None, "period_end": None,
                                     "text": "Je n'ai pas pu etablir une reponse fiable. Pouvez-vous preciser "
                                             "la question (indicateur, site ou borne, periode) ?"}
                    out["fallback_answer"], out["error"] = True, f"secours apres sortie invalide : {exc}"
                    break
                out["retried_format"] = True
                messages.append({"role": "assistant", "content": r.content or ""})
                messages.append({"role": "user", "content": f"Format invalide ({str(exc)[:200]}). "
                                 "Reponds uniquement par l'objet JSON demande."})
                continue
            break
        out["n_steps"] = sum(1 for c in out["calls"] if c["tool_calls"])
        return out
    finally:
        con.close()
