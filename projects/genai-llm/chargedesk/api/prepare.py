"""Prepare les reponses de l'agent aux questions proposees par la page, sur les soirs vitrines.

    python -m api.prepare                # tous les soirs de SHOWCASE
    python -m api.prepare --only 2021-10-05

Reprise automatique : une question deja preparee n'est jamais refaite, et le cache des appels LLM
evite de repayer un appel deja fait. Si le quota du jour est atteint, le script s'arrete proprement :
relancer la meme commande apres le renouvellement du quota.
Ecrit : <donnees>/demo/prepared.json (servi par l'API) et prepared_report.md (a relire avant mise en ligne).
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime

from api.prepared import SHOWCASE, PreparedStore
from api.service import evening_overview
from api.templates import FREQUENT, POST_QUESTIONS, SITE_QUESTIONS
from chargedesk.config import data_dir, load_config, warehouse_path
from chargedesk.llm.client import LLMClient, QuotaExhausted, TransientError
from chargedesk.systems import agent


def questions_for(overview: dict) -> list[str]:
    """Exactement les questions que la page propose ce soir-la (boutons Expliquer, Verifier, questions utiles)."""
    qs = [POST_QUESTIONS[0]["text"].format(post_id=r["post_id"]) for r in overview["list"]]
    qs += [SITE_QUESTIONS[0]["text"].format(site=s["site"]) for s in overview["silent_sites"]]
    qs += [q["text"] for q in FREQUENT]
    return qs


def report(store: PreparedStore) -> str:
    lines = ["# Reponses preparees : a relire avant la mise en ligne", ""]
    for ev in store.evenings():
        lines += [f"## Soir du {ev}", ""]
        for rec in (v for v in store.items.values() if v["evening"] == ev):
            a = rec["answer"] or {}
            figs = ", ".join(f"{f['name']} = {f['value']}" for f in a.get("figures") or [])
            lines += [f"- **{rec['question']}**", f"  - statut : {a.get('status')}",
                      f"  - texte : {a.get('text')}"]
            if figs:
                lines.append(f"  - chiffres : {figs}")
            lines.append(f"  - outils : {', '.join(s['tool'] for s in rec.get('steps', [])) or 'aucun'}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="flash_lite")
    ap.add_argument("--only", nargs="*", help="soirs a preparer (AAAA-MM-JJ)")
    args = ap.parse_args(argv)
    cfg = load_config()
    wh = warehouse_path(cfg)
    folder = data_dir(cfg) / "demo"
    store = PreparedStore(folder / "prepared.json")
    llm = LLMClient.from_config(args.model)          # patience de l'evaluation : on a le temps
    evenings = [date.fromisoformat(d) for d in args.only] if args.only else SHOWCASE
    done = failed = 0
    try:
        for ev in evenings:
            qs = questions_for(evening_overview(wh, ev))
            print(f"\n{ev} : {len(qs)} questions", flush=True)
            for q in qs:
                if store.get(ev, q):
                    continue
                t0 = time.monotonic()
                try:
                    out = agent.run(llm, wh, ev, q)
                except TransientError as exc:
                    failed += 1
                    print(f"  ECHEC (a refaire en relancant) : {q[:70]} ({exc})", flush=True)
                    continue
                if not out.get("answer") or out.get("fallback_answer"):
                    failed += 1
                    print(f"  ILLISIBLE (a refaire) : {q[:70]}", flush=True)
                    continue
                store.put(ev, q, {
                    "answer": out["answer"], "model": args.model, "llm_calls": len(out["calls"]),
                    "steps": [{"tool": t["tool"], "ok": t["ok"]} for t in out.get("tool_trace", [])],
                    "prepared_at": datetime.now().astimezone().isoformat(timespec="minutes")})
                store.save()
                done += 1
                print(f"  ok {out['answer']['status']:9} {time.monotonic() - t0:5.1f} s  {q[:70]}", flush=True)
    except QuotaExhausted as exc:
        print(f"\nARRET : {exc}\nRelancer la meme commande apres le renouvellement du quota (9 h, heure de Paris) :"
              " le travail deja fait est garde.")
    finally:
        if store.items:
            store.save()
            (folder / "prepared_report.md").write_text(report(store), encoding="utf-8")
    total = len(store.items)
    print(f"\n{done} reponses preparees cette fois, {failed} a refaire, {total} au total.")
    print("ecrit :", folder / "prepared.json", "et", folder / "prepared_report.md")


if __name__ == "__main__":
    main()
