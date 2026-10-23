"""Applique la regle de decision fixee AVANT les resultats (cadrage, phase 4).

    python -m chargedesk.eval.decide --split dev [--candidate agent --baseline text_to_sql --model flash_lite]

Regle : le candidat (meme LLM) doit avoir
  1. une exactitude >= reference + 10 points, et un intervalle bootstrap a 95 % de l'ecart qui exclut 0 ;
  2. au plus 2 % de reponses avec un chiffre non etaye ;
  3. au moins 90 % de refus corrects ;
  4. une latence p95 < 10 s.
Le bootstrap tire les QUESTIONS avec remise (les 3 repetitions d'une question restent ensemble) :
c'est la question qui est l'unite, pas la repetition.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import numpy as np

import json

from chargedesk.eval.build_expected import EXPECTED_PATH
from chargedesk.eval.report import load_run, summarize
from chargedesk.eval.run import runs_dir

MIN_GAIN, MAX_UNSUPPORTED, MIN_REFUSALS, MAX_P95 = 0.10, 0.02, 0.90, 10.0


def per_question(rows: list[dict]) -> dict[str, float]:
    by = defaultdict(list)
    for r in rows:
        if not r.get("infra_error"):
            by[r["id"]].append(float(r["grade"]["correct"]))
    return {q: sum(v) / len(v) for q, v in by.items()}


def bootstrap_gain(cand: dict, base: dict, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    ids = sorted(set(cand) & set(base))
    diff = np.array([cand[q] - base[q] for q in ids])
    rng = np.random.default_rng(seed)
    boots = diff[rng.integers(0, len(diff), (n_boot, len(diff)))].mean(axis=1)
    return float(diff.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def decide(cand_rows, base_rows) -> dict:
    s_c, s_b = summarize(cand_rows), summarize(base_rows)
    gain, lo, hi = bootstrap_gain(per_question(cand_rows), per_question(base_rows))
    checks = {
        f"exactitude >= reference + {MIN_GAIN:.0%} et IC sans 0":
            (gain >= MIN_GAIN and lo > 0, f"ecart {gain:+.1%} [IC 95 % {lo:+.1%} ; {hi:+.1%}]"),
        f"chiffres non etayes <= {MAX_UNSUPPORTED:.0%}":
            (s_c["reponses_non_etayees"] <= MAX_UNSUPPORTED, f"{s_c['reponses_non_etayees']:.1%}"),
        f"refus corrects >= {MIN_REFUSALS:.0%}":
            (s_c["refus_corrects"] is not None and s_c["refus_corrects"] >= MIN_REFUSALS,
             "aucune question a refuser" if s_c["refus_corrects"] is None else f"{s_c['refus_corrects']:.0%}"),
        f"latence p95 < {MAX_P95:.0f} s":
            (s_c["latence_p95_s"] < MAX_P95, f"{s_c['latence_p95_s']:.1f} s"),
    }
    return {"candidate": s_c, "baseline": s_b, "checks": checks,
            "verdict": all(ok for ok, _ in checks.values())}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--candidate", default="agent")
    ap.add_argument("--baseline", default="text_to_sql")
    ap.add_argument("--model", default="flash_lite")
    args = ap.parse_args(argv)
    folder = runs_dir()
    meta_c, rows_c = load_run(folder / f"{args.candidate}__{args.model}__{args.split}.jsonl")
    meta_b, rows_b = load_run(folder / f"{args.baseline}__{args.model}__{args.split}.jsonl")
    for m in (meta_c, meta_b):
        if not m["complete"] or any(r.get("infra_error") for r in (rows_c if m is meta_c else rows_b)):
            print(f"ATTENTION : passe {m['system']} incomplete ou avec erreurs techniques ; "
                  "relancer la meme commande avant de conclure.")
    res = decide(rows_c, rows_b)
    print(f"{args.candidate} contre {args.baseline}, LLM {args.model}, split {args.split}\n")
    for name, (ok, val) in res["checks"].items():
        print(f"  [{'OK ' if ok else 'NON'}] {name:45} {val}")
    print("\nVerdict :", "regle satisfaite" if res["verdict"] else "regle NON satisfaite")
    print(f"Conditions : {meta_c.get('started_local', '?')}, plancher serveur {meta_c.get('server_floor_s', '?')} s")
    fails = [r for r in rows_c if not r.get("infra_error") and not r["grade"]["correct"]]
    if fails:
        exp = {i["id"]: i["expected"] for i in json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))["items"]}
        print("\nReponses fausses du candidat :")
        for r in fails:
            a = r["answer"] or {}
            e = exp.get(r["id"], {})
            print(f"\n  {r['id']} rep{r['rep']} ({r['category']}) attendu {r['expected_status']}, obtenu {a.get('status')}")
            print(f"      attendu  : {[(f['name'], f['value'], f['unit']) for f in e.get('figures', [])]}")
            print(f"      donne    : {[(f['name'], f['value'], f['unit']) for f in a.get('figures') or []]}")
            print(f"      texte    : {(a.get('text') or r.get('error') or '')[:300]}")
            for t in r.get("tool_trace") or []:
                res = t["result"]
                print(f"      outil    : {t['tool']} {t['arguments']} -> "
                      f"{'ERREUR ' + res['error'][:150] if not t['ok'] else json.dumps(res, ensure_ascii=False)[:250]}")

if __name__ == "__main__":
    main()
