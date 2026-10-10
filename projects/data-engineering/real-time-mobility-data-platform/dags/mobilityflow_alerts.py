"""Alerte minimale du DAG MobilityFlow : écrire une ligne dans un journal quand une tâche échoue.

Ce fichier ne dépend pas d'Airflow : il peut être testé seul.
Le journal est <données>/monitoring/failures.log (une ligne JSON par échec).
Dans le conteneur, <données> est /data (variable MOBILITYFLOW_DATA_DIR).
Le script monitoring/health_check.py lit ce journal.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def alert_log_path() -> Path:
    return Path(os.environ.get("MOBILITYFLOW_DATA_DIR", "/data")) / "monitoring" / "failures.log"


def log_failure(context: dict) -> None:
    """Appelée par Airflow quand une tâche a échoué pour de bon. Ne doit JAMAIS lever d'erreur."""
    try:
        ti = context.get("task_instance")
        record = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "dag": getattr(ti, "dag_id", None) or str(context.get("dag")),
            "task": getattr(ti, "task_id", None),
            "run": str(context.get("run_id")),
        }
        path = alert_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # une alerte ne doit pas faire échouer le pipeline en plus
        print(f"log_failure: impossible d'écrire l'alerte : {exc}")