"""MobilityFlow - exploration des relevés collectés (station_status).

Lit tous les fichiers JSON collectés, les assemble dans un tableau et affiche
un résumé : combien de relevés, quelles stations sont fermées, quelles stations
ont un dernier relevé ancien, etc. Rien n'est modifié ni écrit.

Usage :
    python explore.py --data C:\\dev\\mobilityflow-data
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

STALE_HOURS = 6  # seuil EXPLORATOIRE : à ajuster après avoir regardé les données


def load_snapshots(data_dir: Path) -> pd.DataFrame:
    """Un fichier JSON = un instantané du réseau. On les empile dans un seul tableau."""
    files = sorted((data_dir / "gbfs" / "nantes" / "station_status").glob("date=*/*.json"))
    if not files:
        sys.exit(f"Aucun fichier trouvé sous {data_dir}\\gbfs\\nantes\\station_status")

    frames, skipped = [], 0
    for path in files:
        day = path.parent.name.removeprefix("date=")  # ex. 2026-10-09
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            df = pd.DataFrame(payload["data"]["stations"])
        except Exception as exc:  # fichier abîmé ou format inattendu : on le saute
            skipped += 1
            print(f"  ! fichier ignoré {path.name} : {exc}")
            continue
        # Heure de collecte (UTC) = date du dossier + heure dans le nom du fichier.
        df["ingested_at"] = pd.to_datetime(f"{day} {path.stem}", format="%Y-%m-%d %H%M%S", utc=True)
        frames.append(df)

    print(f"{len(files)} fichiers lus, {skipped} ignorés")
    return pd.concat(frames, ignore_index=True)


def add_quality_columns(df: pd.DataFrame) -> pd.DataFrame:
    # last_reported : secondes depuis 1970. Une valeur <= 0 est une valeur factice
    # (ex. station jamais installée) : on la remplace par "inconnu".
    reported = df["last_reported"].where(df["last_reported"] > 0)
    df["last_reported_at"] = pd.to_datetime(reported, unit="s", utc=True)
    df["hours_since_last_report"] = (df["ingested_at"] - df["last_reported_at"]).dt.total_seconds() / 3600
    df["is_working"] = df["is_installed"] & df["is_renting"]
    df["is_empty"] = df["num_bikes_available"] == 0
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dossier des données collectées")
    args = parser.parse_args()

    df = add_quality_columns(load_snapshots(Path(args.data)))

    print("\n=== Vue d'ensemble ===")
    print(f"Période (UTC)      : {df['ingested_at'].min()}  ->  {df['ingested_at'].max()}")
    print(f"Instantanés        : {df['ingested_at'].nunique()}")
    print(f"Stations distinctes: {df['station_id'].nunique()}")
    print(f"Lignes au total    : {len(df)}")

    last = df[df["ingested_at"] == df["ingested_at"].max()]
    print("\n=== Dernier instantané ===")
    print(f"Stations non installées      : {(~last['is_installed']).sum()}")
    print(f"Stations installées mais fermées à la location : {(last['is_installed'] & ~last['is_renting']).sum()}")
    print(f"Stations en service          : {last['is_working'].sum()}")
    print(f"  dont vides (0 vélo)        : {(last['is_working'] & last['is_empty']).sum()}")
    print(f"  dont sans place libre      : {(last['is_working'] & (last['num_docks_available'] == 0)).sum()}")
    print(f"Dernier relevé inconnu (valeur factice) : {last['last_reported_at'].isna().sum()}")
    print(f"Dernier relevé de plus de {STALE_HOURS} h  : {(last['hours_since_last_report'] > STALE_HOURS).sum()}")

    print("\n=== 10 stations au dernier relevé le plus ancien ===")
    cols = ["station_id", "num_bikes_available", "is_installed", "is_renting", "hours_since_last_report"]
    print(last.sort_values("hours_since_last_report", ascending=False)[cols].head(10).round(1).to_string(index=False))

    if df["ingested_at"].nunique() > 1:
        # Un relevé qui ne change jamais est-il un signe de panne, ou juste une station calme ?
        stuck = df.groupby("station_id")["last_reported"].nunique()
        print("\n=== Stations dont last_reported n'a JAMAIS changé pendant la période ===")
        print(f"{(stuck == 1).sum()} stations sur {len(stuck)}")

        # Le test décisif : le nombre de vélos bouge-t-il alors que last_reported ne bouge pas ?
        # Si oui, last_reported n'est pas fiable pour mesurer la fraîcheur d'une station.
        ordered = df.sort_values(["station_id", "ingested_at"])
        grouped = ordered.groupby("station_id")
        bikes_changed = grouped["num_bikes_available"].diff().fillna(0) != 0
        report_changed = grouped["last_reported"].diff().fillna(0) != 0
        print("\n=== Test de fiabilité de last_reported ===")
        print(f"Changements du nombre de vélos           : {bikes_changed.sum()}")
        print(f"  dont SANS changement de last_reported  : {(bikes_changed & ~report_changed).sum()}")


if __name__ == "__main__":
    main()
