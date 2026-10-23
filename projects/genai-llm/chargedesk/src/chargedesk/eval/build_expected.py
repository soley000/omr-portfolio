"""Calcule les reponses attendues du jeu d'evaluation.

Pour chaque question, chaque requete est executee deux fois :
1. sur l'entrepot vu depuis le soir de la question (snapshot) : c'est la
   reponse attendue, qui ne peut pas contenir d'information future ;
2. sur l'entrepot complet : si le resultat differe, la question depend du
   futur (fuite) et la construction s'arrete.

Une requete doit renvoyer une seule ligne et une seule colonne `value`, non
vide. Le resultat est ecrit dans eval/expected.json, avec l'empreinte du
fichier de questions et celles des sources de l'entrepot.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from chargedesk.config import PROJECT_ROOT, load_config, warehouse_path
from chargedesk.data.snapshot import full_connection, snapshot_connection
from chargedesk.eval.questions import QUESTIONS_PATH, Question, check_plan, load_questions

EXPECTED_PATH = PROJECT_ROOT / "eval" / "expected.json"


class GoldError(Exception):
    pass


def scalar(con, sql: str, qid: str, name: str) -> float:
    rows = con.execute(sql).fetchall()
    if len(rows) != 1 or len(rows[0]) != 1:
        raise GoldError(f"{qid} / {name} : la requete doit renvoyer une seule valeur (recu {len(rows)} ligne(s))")
    v = rows[0][0]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        raise GoldError(f"{qid} / {name} : valeur vide, la question n'a pas de reponse ce soir-la")
    return float(v)


def build(questions: list[Question], warehouse: Path, errors: list[str] | None = None) -> list[dict]:
    """Calcule les reponses attendues.

    Sans `errors`, s'arrete au premier probleme (GoldError). Avec une liste
    `errors`, note chaque probleme et continue, pour tout voir d'un coup.
    """
    full = full_connection(warehouse)
    out = []
    try:
        for q in questions:
            figures = []
            failed = False
            if q.figures:
                snap = snapshot_connection(warehouse, q.evening)
                try:
                    for f in q.figures:
                        try:
                            value = scalar(snap, f.sql, q.id, f.name)
                            value_full = scalar(full, f.sql, q.id, f.name)
                            if not math.isclose(value, value_full, rel_tol=0, abs_tol=1e-9):
                                raise GoldError(
                                    f"{q.id} / {f.name} : fuite, {value} vu le soir de la question "
                                    f"contre {value_full} avec tout l'entrepot")
                        except GoldError as exc:
                            if errors is None:
                                raise
                            errors.append(str(exc))
                            failed = True
                            continue
                        figures.append({"name": f.name, "value": value, "unit": f.unit})
                finally:
                    snap.close()
            if failed:
                continue
            out.append({
                "id": q.id, "split": q.split, "evening": q.evening.isoformat(),
                "category": q.category, "question": q.question,
                "expected": {"status": q.expected_status, "figures": figures,
                             "refusal_reason": q.refusal_reason},
            })
    finally:
        full.close()
    return out


def sha256_file(path: Path) -> str:
    """Empreinte du fichier, fins de ligne normalisees (identique sous Windows et dans la CI)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> None:
    cfg = load_config()
    questions = load_questions()
    problems = check_plan(questions, cfg["evaluation"])
    if problems:
        raise SystemExit("Le jeu ne respecte pas le plan :\n- " + "\n- ".join(problems))

    wh = warehouse_path(cfg)
    errors: list[str] = []
    items = build(questions, wh, errors)
    if errors:
        raise SystemExit(f"{len(errors)} probleme(s), expected.json n'est pas ecrit :\n- " + "\n- ".join(errors))

    con = full_connection(wh)
    load_log = {s: h for s, h in con.execute("select source, sha256 from raw.load_log").fetchall()}
    con.close()

    payload = {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "questions_sha256": sha256_file(QUESTIONS_PATH),
        "sources_sha256": load_log,
        "items": items,
    }
    EXPECTED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(items)} questions : " + ", ".join(f"{k} {v}" for k, v in Counter(i["split"] for i in items).items()))
    for i in items:
        figs = "; ".join(f"{f['name']} = {f['value']:g}" for f in i["expected"]["figures"])
        extra = figs or i["expected"]["status"] + (f" ({i['expected']['refusal_reason']})" if i["expected"]["refusal_reason"] else "")
        zero = "  <-- zero, a verifier" if any(f["value"] == 0 for f in i["expected"]["figures"]) else ""
        print(f"{i['id']:8} {i['evening']}  {extra}{zero}")
    print("ecrit :", EXPECTED_PATH)
    print("empreinte des questions :", payload["questions_sha256"][:12])


if __name__ == "__main__":
    main()
