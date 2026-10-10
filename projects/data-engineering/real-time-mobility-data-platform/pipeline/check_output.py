"""MobilityFlow - controle apres conversion : le Parquet du jour existe et contient des lignes.

Sort avec un code d'erreur (1) sinon : Airflow marque alors la tache en ECHEC (rouge).

Usage : python check_output.py --data C:\\dev\\mobilityflow-data --date 2026-10-09
"""
import argparse
import sys
from pathlib import Path

import pandas as pd


def check(data_dir: Path, day: str) -> str | None:
    """Renvoie un message d'erreur, ou None si tout va bien."""
    path = data_dir / "parquet" / "station_status" / f"date_paris={day}" / "station_status.parquet"
    if not path.exists():
        return f"fichier absent : {path}"
    df = pd.read_parquet(path, columns=["station_id", "snapshot_ts"])
    if df.empty:
        return f"fichier vide : {path}"
    print(f"OK {day} : {len(df)} lignes, {df['snapshot_ts'].nunique()} releves, {df['station_id'].nunique()} stations")
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    error = check(Path(args.data), args.date)
    if error:
        print("ECHEC :", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
