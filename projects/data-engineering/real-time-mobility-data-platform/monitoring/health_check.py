"""MobilityFlow - contrôle de santé : tout tourne-t-il comme prévu ?

Quatre contrôles, en une commande :
  1. Le collecteur est-il vivant ?            (dernier relevé brut de moins de 5 minutes)
  2. La collecte est-elle complète ?          (au moins 55 relevés sur la dernière heure)
  3. L'entrepôt a-t-il été publié récemment ? (moins de 30 heures ; Airflow le met à jour à 3 h)
  4. Une tâche Airflow a-t-elle échoué ?      (journal failures.log, dernières 24 heures)

Résultat : une ligne par contrôle (OK / ATTENTION / ALERTE). Code de sortie 1 s'il y a une ALERTE.

Usage :
    python monitoring\\health_check.py                       # dossier par défaut
    python monitoring\\health_check.py --data C:\\dev\\mobilityflow-data
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

OK, WARN, ALERT = "OK", "ATTENTION", "ALERTE"


@dataclass
class Check:
    name: str
    level: str
    detail: str


def _age_text(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes} min" if minutes < 120 else f"{minutes // 60} h {minutes % 60:02d}"


# ----------------------------------------------------------------------- règles (testables)

def collector_check(now: datetime, newest_raw: datetime | None, max_minutes: int = 5) -> Check:
    name = "Collecteur vivant"
    if newest_raw is None:
        return Check(name, ALERT, "aucun releve brut trouve")
    age = now - newest_raw
    if age > timedelta(minutes=max_minutes):
        return Check(name, ALERT, f"dernier releve il y a {_age_text(age)} (le collecteur est-il arrete ?)")
    return Check(name, OK, f"dernier releve il y a {_age_text(age)}")


def completeness_check(files_last_hour: int, minimum: int = 55) -> Check:
    name = "Collecte complete (derniere heure)"
    if files_last_hour < minimum:
        return Check(name, WARN, f"{files_last_hour} releves sur 60 attendus")
    return Check(name, OK, f"{files_last_hour} releves sur 60 attendus")


def warehouse_check(now: datetime, warehouse_time: datetime | None, max_hours: int = 30) -> Check:
    name = "Entrepot a jour"
    if warehouse_time is None:
        return Check(name, ALERT, "fichier mobilityflow.duckdb introuvable (Airflow n'a pas encore publie ?)")
    age = now - warehouse_time
    if age > timedelta(hours=max_hours):
        return Check(name, ALERT, f"derniere publication il y a {_age_text(age)} (Airflow a-t-il tourne cette nuit ?)")
    return Check(name, OK, f"derniere publication il y a {_age_text(age)}")


def failures_check(now: datetime, failures: list[dict], window_hours: int = 24) -> Check:
    name = "Echecs Airflow (24 h)"
    recent = []
    for rec in failures:
        try:
            when = datetime.fromisoformat(rec["time"])
        except (KeyError, ValueError):
            continue
        if now - when <= timedelta(hours=window_hours):
            recent.append(rec)
    if recent:
        last = recent[-1]
        return Check(name, ALERT, f"{len(recent)} echec(s), dernier : tache {last.get('task')} ({last.get('time')})")
    return Check(name, OK, "aucun echec")


# ----------------------------------------------------------------------- lecture du disque

def _latest_raw_files(data_dir: Path) -> list[Path]:
    base = data_dir / "gbfs" / "nantes" / "station_status"
    folders = sorted(base.glob("date=*"))[-2:]          # aujourd'hui et la veille (UTC) suffisent
    return [p for folder in folders for p in folder.glob("*.json")]


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def read_failures(data_dir: Path) -> list[dict]:
    log = data_dir / "monitoring" / "failures.log"
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def run_checks(data_dir: Path, now: datetime | None = None) -> list[Check]:
    now = now or datetime.now(timezone.utc)
    files = _latest_raw_files(data_dir)
    times = [_mtime(p) for p in files]
    newest = max(times) if times else None
    last_hour = sum(1 for t in times if now - t <= timedelta(hours=1))
    warehouse = data_dir / "warehouse" / "mobilityflow.duckdb"
    return [
        collector_check(now, newest),
        completeness_check(last_hour),
        warehouse_check(now, _mtime(warehouse) if warehouse.exists() else None),
        failures_check(now, read_failures(data_dir)),
    ]


def main() -> None:
    default = os.environ.get("MOBILITYFLOW_DATA_DIR", "C:/dev/mobilityflow-data")
    parser = argparse.ArgumentParser(description="Controle de sante de MobilityFlow")
    parser.add_argument("--data", default=default, help="dossier des donnees (celui du collecteur)")
    args = parser.parse_args()

    checks = run_checks(Path(args.data))
    for c in checks:
        print(f"[{c.level:<9}] {c.name} : {c.detail}")
    sys.exit(1 if any(c.level == ALERT for c in checks) else 0)


if __name__ == "__main__":
    main()