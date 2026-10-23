"""Fait passer le jeu d'evaluation a un systeme, avec un LLM, et note chaque reponse.

    python -m chargedesk.eval.run --system no_tools --model flash_lite --split dev --reps 3

- Les appels deja faits sont relus dans le cache : une passe interrompue
  (quota du jour) se relance avec la meme commande et reprend ou elle en etait.
- Le jeu de TEST ne s'ouvre qu'une fois par couple (systeme, modele), avec
  --final-test ; l'ouverture est inscrite dans runs/test_openings.json.
- Resultats : runs/<systeme>__<modele>__<split>.jsonl (une ligne par question et repetition).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from chargedesk.config import data_dir, load_config, warehouse_path
from chargedesk.eval.build_expected import EXPECTED_PATH
from chargedesk.eval.grading import grade
from chargedesk.eval.schema import Answer, Expected
from chargedesk.llm.client import LLMClient, QuotaExhausted, TransientError
from chargedesk.systems import agent, no_tools, text_to_sql

SYSTEMS = {no_tools.NAME: no_tools, text_to_sql.NAME: text_to_sql, agent.NAME: agent}


def runs_dir() -> Path:
    d = data_dir(load_config()) / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def guard_test_opening(system: str, model: str, confirmed: bool, folder: Path) -> None:
    registry = folder / "test_openings.json"
    opened = json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {}
    key = f"{system}__{model}"
    if not confirmed:
        raise SystemExit("Le jeu de test ne s'ouvre qu'une fois, a la fin : ajouter --final-test pour le confirmer.")
    if key in opened:
        # reprise permise seulement si la passe ouverte a ete interrompue (quota, erreurs techniques) :
        # le cache rejoue les reponses deja obtenues, rien n'est refait ni retouche
        out = folder / f"{key}__test.jsonl"
        lines = out.read_text(encoding="utf-8").splitlines() if out.exists() else []
        meta = json.loads(lines[0])["meta"] if lines else {"complete": False}
        infra = any(json.loads(l).get("infra_error") for l in lines[1:])
        if meta.get("complete") and not infra:
            raise SystemExit(f"Test deja ouvert et termine pour {key} le {opened[key]} : on ne le rouvre pas.")
        print(f"Reprise de la passe test {key} ouverte le {opened[key]} (interrompue).")
        return
    opened[key] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registry.write_text(json.dumps(opened, indent=1), encoding="utf-8")


def run_one(system_mod, llm, warehouse, item: dict, rep: int) -> dict:
    t0 = time.monotonic()
    try:
        out = system_mod.run(llm, warehouse, date.fromisoformat(item["evening"]), item["question"], rep=rep)
    except QuotaExhausted:
        raise
    except TransientError as exc:
        return {"id": item["id"], "category": item["category"], "rep": rep,
                "expected_status": item["expected"]["status"], "answer": None,
                "error": f"technique : {exc}", "infra_error": True, "sql": [], "sql_errors": [],
                "grade": {"status_ok": False, "reason_ok": False, "figures_ok": False,
                          "unsupported": [], "correct": False},
                "n_calls": 0, "latency_s": 0.0, "tokens": 0, "all_cached": False,
                "wall_s": round(time.monotonic() - t0, 3)}
    except Exception as exc:
        out = {"calls": [], "tool_results": [], "sql": [], "sql_errors": [], "answer": None,
               "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    expected = Expected(**item["expected"])
    if out.get("answer"):
        g = grade(Answer(**out["answer"]), expected, out["tool_results"]).model_dump()
    else:
        g = {"status_ok": False, "reason_ok": False, "figures_ok": False, "unsupported": [], "correct": False}
    calls = out["calls"]
    return {
        "id": item["id"], "category": item["category"], "rep": rep,
        "expected_status": expected.status, "answer": out.get("answer"), "error": out.get("error"),
        "infra_error": False,
        "sql": out["sql"], "sql_errors": out["sql_errors"], "grade": g,
        "n_calls": len(calls),
        "latency_s": round(sum(c["latency_s"] for c in calls) + out.get("tool_time_s", 0.0), 3),
        "tool_trace": out.get("tool_trace"),
        "tool_time_s": round(out.get("tool_time_s", 0.0), 3),
        "llm_calls": [{"latency_s": c["latency_s"], "prompt_tokens": c["prompt_tokens"],
                       "completion_tokens": c["completion_tokens"],
                       "reasoning_tokens": c.get("reasoning_tokens", 0), "cached": c.get("cached")}
                      for c in calls],
        "tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls),
        "all_cached": bool(calls) and all(c.get("cached") for c in calls),
        "wall_s": round(time.monotonic() - t0, 3),
    }


def server_floor(model: str, n: int = 3) -> float | None:
    """Mediane du temps d'un appel minuscule, sans cache : l'attente propre au fournisseur a cette heure."""
    try:
        llm = LLMClient.from_config(model, use_cache=False)
        times = sorted(llm.chat([{"role": "user", "content": "Reponds juste OK."}]).latency_s for _ in range(n))
        return round(times[len(times) // 2], 2)
    except (TransientError, QuotaExhausted):
        return None


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="identifiants de questions (essai rapide)")
    ap.add_argument("--final-test", action="store_true")
    ap.add_argument("--label", default="", help="version du systeme (ex. v2) : fichier et nom distincts")
    ap.add_argument("--no-floor", action="store_true", help="ne pas mesurer le plancher du serveur (6 appels)")
    args = ap.parse_args(argv)

    folder = runs_dir()
    if args.split == "test":
        guard_test_opening(args.system, args.model, args.final_test, folder)

    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    items = [i for i in expected["items"] if i["split"] == args.split]
    if args.only:
        items = [i for i in items if i["id"] in set(args.only)]
    llm = LLMClient.from_config(args.model)
    wh = warehouse_path(load_config())
    name = f"{args.system}-{args.label}" if args.label else args.system
    out_path = folder / f"{name}__{args.model}__{args.split}.jsonl"

    started = datetime.now().astimezone()
    floor_start = None if args.no_floor else server_floor(args.model)
    rows = []
    try:
        for rep in range(args.reps):
            for item in items:
                row = run_one(SYSTEMS[args.system], llm, wh, item, rep)
                rows.append(row)
                mark = "OK " if row["grade"]["correct"] else "-- "
                print(f"{mark}{row['id']:8} rep{rep}  {row['latency_s']:5.1f}s  "
                      f"{'(cache)' if row['all_cached'] else ''}{row['error'] or ''}"[:150], flush=True)
    except QuotaExhausted as exc:
        print(f"\nARRET : {exc}\nRelancer la meme commande plus tard : le cache reprend ou on en etait.")
    floor_end = None if args.no_floor else server_floor(args.model)
    meta = {"system": name, "model": args.model, "llm": llm.model, "split": args.split,
            "reps": args.reps, "questions_sha256": expected["questions_sha256"],
            "complete": not args.only and len(rows) == len(items) * args.reps,
            "started_local": started.isoformat(timespec="minutes"),
            "server_floor_s": [floor_start, floor_end],
            "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    infra = sum(1 for r in rows if r.get("infra_error"))
    graded = [r for r in rows if not r.get("infra_error")]
    ok = sum(r["grade"]["correct"] for r in graded)
    print(f"\n{ok}/{len(graded)} justes ({ok / len(graded):.0%})" if graded else "\naucune reponse")
    if infra:
        print(f"{infra} erreur(s) technique(s) (pas de reponse du fournisseur) : relancer la meme commande "
              "pour les refaire, les reponses deja obtenues viennent du cache.")
    if not args.no_floor:
        print(f"plancher du serveur (appel minuscule) : debut {floor_start} s, fin {floor_end} s")
    print("ecrit :", out_path)


if __name__ == "__main__":
    main()
