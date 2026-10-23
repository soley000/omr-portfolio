"""Rapport de surveillance a partir du journal des questions.

    python -m api.report_monitoring                      # journal local (<donnees>/monitoring/questions.jsonl)
    python -m api.report_monitoring --file chemin.jsonl  # un autre journal (ex. extrait des journaux Render)

Repond a : combien de questions, preparees ou en direct ? Combien d'echecs, et pourquoi ? Combien de bascules
vers le repli ? Quels temps de reponse (median, p95), et selon l'heure ? Combien de jetons par question ?
Ecrit aussi <donnees>/monitoring/monitoring_report.md.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

CAUSES = [("quota", "quota épuisé"), ("connexion", "connexion impossible"), ("lent", "trop lent"),
          ("configur", "modèle non configuré"), ("occup", "fournisseur occupé"), ("limite", "limite de la démo")]


def p95(values: list[float]) -> float | None:
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))] if v else None


def load(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = re.search(r"\{.*\}$", line)          # accepte aussi des lignes de journal Render ("... question {json}")
        if m:
            try:
                rows.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                continue
    return rows


def cause(row: dict) -> str:
    text = (row.get("error") or "") + " " + " ".join(row.get("notes") or [])
    for key, label in CAUSES:
        if key in text.lower():
            return label
    return "autre" if row.get("http") != 200 else "aucune"


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    live = [r for r in rows if r.get("source") == "direct"]
    live_ok = [r for r in live if r.get("http") == 200]
    by_hour = defaultdict(list)
    for r in live_ok:
        by_hour[int(r["ts"][11:13])].append(r["latency_s"])
    return {
        "periode": (rows[0]["ts"], rows[-1]["ts"]) if rows else None,
        "questions": n,
        "preparees": sum(1 for r in rows if r.get("source") == "preparee"),
        "en_direct": len(live),
        "refusees_limite": sum(1 for r in rows if r.get("http") == 429),
        "echecs_direct": sum(1 for r in live if r.get("http") != 200),
        "causes_echec": Counter(cause(r) for r in rows if r.get("http") not in (200, None)),
        "bascules_repli": sum(1 for r in live_ok if r.get("fallback_used")),
        "incidents_rattrapes": Counter(cause(r) for r in live_ok if r.get("notes")),
        "statuts": Counter(r.get("status") for r in rows if r.get("http") == 200),
        "latence_direct_mediane_s": median([r["latency_s"] for r in live_ok]) if live_ok else None,
        "latence_direct_p95_s": p95([r["latency_s"] for r in live_ok]),
        "latence_par_heure_utc": {h: round(median(v), 1) for h, v in sorted(by_hour.items())},
        "jetons_par_question_direct": median([r.get("tokens", 0) for r in live_ok]) if live_ok else None,
        "outils": Counter(t for r in rows for t in (r.get("tools") or [])),
        "modeles": Counter(r.get("model") for r in live_ok),
    }


def to_markdown(s: dict) -> str:
    pct = lambda a, b: f"{100 * a / b:.0f} %" if b else "—"
    L = ["# ChargeDesk : rapport de surveillance", ""]
    if not s["questions"]:
        return "\n".join(L + ["Aucune question dans le journal."])
    L += [f"Période : {s['periode'][0]} → {s['periode'][1]} (UTC)", "",
          "| Indicateur | Valeur |", "|---|---|",
          f"| Questions | {s['questions']} |",
          f"| Réponses préparées (instantanées) | {s['preparees']} ({pct(s['preparees'], s['questions'])}) |",
          f"| Questions en direct | {s['en_direct']} |",
          f"| Échecs en direct | {s['echecs_direct']} ({pct(s['echecs_direct'], s['en_direct'])}) |",
          f"| Refusées (limite de la démo) | {s['refusees_limite']} |",
          f"| Bascules vers le repli | {s['bascules_repli']} |",
          f"| Temps de réponse en direct, médiane / p95 | {s['latence_direct_mediane_s']} s / {s['latence_direct_p95_s']} s |",
          f"| Jetons par question en direct (médiane) | {s['jetons_par_question_direct']} |", ""]
    if s["causes_echec"]:
        L += ["**Causes des échecs** : " + ", ".join(f"{k} ({v})" for k, v in s["causes_echec"].most_common()), ""]
    if s["incidents_rattrapes"]:
        L += ["**Incidents rattrapés par le repli** : "
              + ", ".join(f"{k} ({v})" for k, v in s["incidents_rattrapes"].most_common()), ""]
    if s["latence_par_heure_utc"]:
        L += ["**Temps médian selon l'heure (UTC)** : "
              + ", ".join(f"{h} h : {v} s" for h, v in s["latence_par_heure_utc"].items()), ""]
    L += ["**Statuts des réponses** : " + ", ".join(f"{k} ({v})" for k, v in s["statuts"].most_common()),
          "", "**Outils les plus utilisés** : " + ", ".join(f"{k} ({v})" for k, v in s["outils"].most_common(6))]
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    args = ap.parse_args(argv)
    if args.file:
        path = Path(args.file)
    else:
        from chargedesk.config import data_dir, load_config
        path = data_dir(load_config()) / "monitoring" / "questions.jsonl"
    if not path.exists():
        print("pas encore de journal :", path)
        return
    md = to_markdown(summarize(load(path)))
    out = path.with_name("monitoring_report.md")
    out.write_text(md, encoding="utf-8")
    print(md)
    print("ecrit :", out)


if __name__ == "__main__":
    main()
