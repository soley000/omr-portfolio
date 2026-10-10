"""MobilityFlow - coup d'oeil rapide sur les données (rien n'est modifié).

Affiche :
  1. un extrait du référentiel des stations (station_information)
  2. les informations générales du réseau (system_information)
  3. un contrôle des fichiers Parquet avec DuckDB (nombre de lignes, période...)

Usage :
    python peek.py --data C:\\dev\\mobilityflow-data
"""

import argparse
import json
from pathlib import Path

import duckdb


def latest_json(data_dir: Path, feed: str):
    files = sorted((data_dir / "gbfs" / "nantes" / feed).glob("date=*/*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dossier des données du collecteur")
    args = parser.parse_args()
    data_dir = Path(args.data)

    info = latest_json(data_dir, "station_information")
    print("=== station_information ===")
    if info is None:
        print("aucun fichier")
    else:
        stations = info["data"]["stations"]
        print("Clés générales :", {k: v for k, v in info.items() if k != "data"})
        print("Nombre de stations :", len(stations))
        print("Champs d'une station :", sorted(stations[0].keys()))
        print("Deux exemples :")
        print(json.dumps(stations[:2], indent=1, ensure_ascii=False))

    system = latest_json(data_dir, "system_information")
    print("\n=== system_information ===")
    print(json.dumps(system["data"], indent=1, ensure_ascii=False) if system else "aucun fichier")

    print("\n=== Contrôle des fichiers Parquet (DuckDB) ===")
    pattern = (data_dir / "parquet" / "station_status" / "*" / "*.parquet").as_posix()
    duckdb.sql(
        f"""
        SELECT count(*)                       AS lignes,
               count(DISTINCT station_id)     AS stations,
               count(DISTINCT snapshot_ts)    AS releves,
               min(snapshot_ts)               AS premier_releve_utc,
               max(snapshot_ts)               AS dernier_releve_utc
        FROM read_parquet('{pattern}')
        """
    ).show()


if __name__ == "__main__":
    main()
