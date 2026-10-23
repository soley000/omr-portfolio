"""Tableau de synthese des passes d'evaluation (runs/*.jsonl).

    python -m chargedesk.eval.report --split dev
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from statistics import median

from chargedesk.eval.run import runs_dir

ANSWERABLE = {"fact", "comparison", "list", "alert", "reliability"}


def load_run(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0])["meta"], [json.loads(l) for l in lines[1:]]


def p95(values):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))] if v else None


def summarize(all_rows: list[dict]) -> dict:
    """Les erreurs techniques (aucune reponse du fournisseur) sont comptees a part, pas comme fausses."""
    rows = [r for r in all_rows if not r.get("infra_error")]
    n = len(rows)
    ans = [r for r in rows if r["category"] in ANSWERABLE]
    ref = [r for r in rows if r["expected_status"] == "refuse"]
    cla = [r for r in rows if r["expected_status"] == "clarify"]
    with_figs = [r for r in rows if r["answer"] and r["answer"].get("figures")]
    sql_runs = [r for r in rows if r["sql"]]
    return {
        "n": n,
        "erreurs_techniques": (len(all_rows) - n) / len(all_rows) if all_rows else None,
        "exactitude": sum(r["grade"]["correct"] for r in rows) / n if n else None,
        "exactitude_repondables": sum(r["grade"]["correct"] for r in ans) / len(ans) if ans else None,
        "refus_corrects": sum(r["grade"]["correct"] for r in ref) / len(ref) if ref else None,
        "clarifications": sum(r["grade"]["correct"] for r in cla) / len(cla) if cla else None,
        "faux_refus": sum(1 for r in ans if r["answer"] and r["answer"]["status"] == "refuse") / len(ans) if ans else None,
        "reponses_non_etayees": sum(1 for r in with_figs if r["grade"]["unsupported"]) / n if n else None,
        "sorties_invalides": sum(1 for r in rows if r["answer"] is None) / n if n else None,
        "sql_valides": sum(1 for r in sql_runs if len(r["sql"]) > len(r["sql_errors"])) / len(sql_runs) if sql_runs else None,
        "latence_mediane_s": median([r["latency_s"] for r in rows]) if rows else None,
        "latence_p95_s": p95([r["latency_s"] for r in rows]),
        "jetons_par_question": sum(r["tokens"] for r in rows) / n if n else None,
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    args = ap.parse_args(argv)
    paths = sorted(runs_dir().glob(f"*__{args.split}.jsonl"))
    if not paths:
        print("aucune passe pour", args.split)
        return
    table = {}
    for p in paths:
        meta, rows = load_run(p)
        s = summarize(rows)
        table[f"{meta['system']} / {meta['model']}" + ("" if meta["complete"] else " (incomplet)")] = s
    keys = list(next(iter(table.values())).keys())
    width = max(len(k) for k in table) + 2
    print("".ljust(24) + "".join(k.ljust(width) for k in table))
    for k in keys:
        cells = []
        for s in table.values():
            v = s[k]
            cells.append(("-" if v is None else f"{v:.0%}" if isinstance(v, float) and k not in
                          ("latence_mediane_s", "latence_p95_s", "jetons_par_question") else
                          f"{v:.1f}" if isinstance(v, float) else str(v)).ljust(width))
        print(k.ljust(24) + "".join(cells))
    print("\nConditions de mesure (heure de debut, plancher du serveur debut / fin en s) :")
    for p in paths:
        meta, _ = load_run(p)
        print(f"  {meta['system']} / {meta['model']} : {meta.get('started_local', '?')}, "
              f"{meta.get('server_floor_s', '?')}")
    print("\nPar categorie (exactitude) :")
    for name, p in zip(table, paths):
        _, rows = load_run(p)
        by = defaultdict(list)
        for r in rows:
            if not r.get("infra_error"):
                by[r["category"]].append(r["grade"]["correct"])
        print(f"  {name} : " + ", ".join(f"{c} {sum(v)}/{len(v)}" for c, v in sorted(by.items())))


if __name__ == "__main__":
    main()
