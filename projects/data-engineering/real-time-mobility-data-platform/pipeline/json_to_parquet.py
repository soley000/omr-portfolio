"""MobilityFlow - couche 2 : fichiers JSON bruts -> fichiers Parquet propres.

Deux flux sont convertis :
  - station_status      : l'état des stations à chaque relevé (vélos, places libres, ouverte/fermée)
  - station_information : le référentiel des stations (nom, adresse, position, capacité)

Les fichiers Parquet sont écrits par JOUR (jour de Paris) dans :
    <data>/parquet/<flux>/date_paris=AAAA-MM-JJ/<flux>.parquet

Le script est RELANÇABLE sans risque : relancer un jour remplace simplement le
fichier de ce jour (important pour qu'Airflow puisse le rejouer plus tard).
Les fichiers bruts ne sont jamais modifiés.

Usage :
    python json_to_parquet.py --data C:\\dev\\mobilityflow-data                        # tout, tous les jours
    python json_to_parquet.py --data C:\\dev\\mobilityflow-data --date 2026-10-09      # un seul jour
    python json_to_parquet.py --data C:\\dev\\mobilityflow-data --feed station_status  # un seul flux
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PARIS = "Europe/Paris"

STATUS_COLUMNS = [
    "station_id",
    "num_bikes_available",
    "num_bikes_disabled",
    "num_docks_available",
    "num_docks_disabled",
    "is_installed",
    "is_renting",
    "is_returning",
    "last_reported",
    "snapshot_ts",
    "source_last_updated",
    "bikes_mechanical",
]

INFO_COLUMNS = ["station_id", "name", "address", "lat", "lon", "capacity", "rental_methods", "snapshot_ts"]


# --------------------------------------------------------------------------- lecture

def raw_files(data_dir: Path, feed: str, paris_day: str | None) -> list[Path]:
    base = data_dir / "gbfs" / "nantes" / feed
    if paris_day is None:
        return sorted(base.glob("date=*/*.json"))
    # Un jour de Paris commence la veille en UTC (22h ou 23h) : on lit donc 2 dossiers UTC.
    day = date.fromisoformat(paris_day)
    folders = [base / f"date={day + timedelta(days=k)}" for k in (-1, 0)]
    return sorted(p for folder in folders if folder.exists() for p in folder.glob("*.json"))


def read_payload(path: Path) -> tuple[dict, pd.DataFrame, pd.Timestamp]:
    utc_day = path.parent.name.removeprefix("date=")
    payload = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload["data"]["stations"])
    # Heure de collecte (UTC) = date du dossier + heure dans le nom du fichier.
    snapshot_ts = pd.to_datetime(f"{utc_day} {path.stem}", format="%Y-%m-%d %H%M%S", utc=True)
    return payload, df, snapshot_ts


def count_type(items, type_id: str) -> int:
    if not isinstance(items, list):
        return 0
    return sum(item.get("count", 0) for item in items if item.get("vehicle_type_id") == type_id)


def parse_status(path: Path) -> pd.DataFrame:
    payload, df, snapshot_ts = read_payload(path)
    df["snapshot_ts"] = snapshot_ts
    # Heure de mise à jour annoncée par la source elle-même.
    df["source_last_updated"] = pd.to_datetime(payload.get("last_updated"), unit="s", utc=True)
    types = df["vehicle_types_available"] if "vehicle_types_available" in df else pd.Series([None] * len(df))
    df["bikes_mechanical"] = types.apply(lambda items: count_type(items, "mechanical"))
    return df.reindex(columns=STATUS_COLUMNS)


def parse_info(path: Path) -> pd.DataFrame:
    _, df, snapshot_ts = read_payload(path)
    df["snapshot_ts"] = snapshot_ts
    if "rental_methods" in df:  # absent pour certaines stations : on garde "inconnu"
        df["rental_methods"] = df["rental_methods"].apply(lambda m: ",".join(m) if isinstance(m, list) else None)
    return df.reindex(columns=INFO_COLUMNS)


# --------------------------------------------------------------------------- nettoyage

def add_paris_day(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    df = df.drop_duplicates(subset=keys)
    df["date_paris"] = df["snapshot_ts"].dt.tz_convert(PARIS).dt.strftime("%Y-%m-%d")
    return df.sort_values(["snapshot_ts", "station_id"]).reset_index(drop=True)


def clean_status(df: pd.DataFrame) -> pd.DataFrame:
    # last_reported : secondes depuis 1970 ; une valeur <= 0 est factice -> inconnu.
    reported = pd.to_numeric(df["last_reported"], errors="coerce")
    df["last_reported_at"] = pd.to_datetime(reported.where(reported > 0), unit="s", utc=True)
    df = df.drop(columns=["last_reported"])

    df["station_id"] = df["station_id"].astype("string")
    for col in ["num_bikes_available", "num_bikes_disabled", "num_docks_available", "num_docks_disabled", "bikes_mechanical"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ["is_installed", "is_renting", "is_returning"]:
        df[col] = df[col].astype("boolean")
    return add_paris_day(df, ["station_id", "snapshot_ts"])


def clean_info(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["station_id", "name", "address", "rental_methods"]:
        df[col] = df[col].astype("string")
    for col in ["lat", "lon"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce").astype("Int64")
    return add_paris_day(df, ["station_id", "snapshot_ts"])


FEEDS = {
    "station_status": (parse_status, clean_status),
    "station_information": (parse_info, clean_info),
}


# --------------------------------------------------------------------------- écriture

def write_partitions(df: pd.DataFrame, feed: str, out_dir: Path) -> None:
    for day, part in df.groupby("date_paris"):
        folder = out_dir / "parquet" / feed / f"date_paris={day}"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{feed}.parquet"
        tmp = target.with_suffix(".tmp")
        part.drop(columns=["date_paris"]).to_parquet(tmp, index=False)
        tmp.replace(target)  # remplace le fichier du jour d'un seul coup
        print(f"  {day} : {len(part):>8} lignes, {part['snapshot_ts'].nunique():>5} relevés -> {target}")


def convert(feed: str, data_dir: Path, paris_day: str | None) -> None:
    parse, clean = FEEDS[feed]
    files = raw_files(data_dir, feed, paris_day)
    print(f"\n=== {feed} ===")
    if not files:
        print("Aucun fichier brut trouvé pour cette sélection.")
        return

    frames, skipped = [], 0
    for path in files:
        try:
            frames.append(parse(path))
        except Exception as exc:  # fichier abîmé : on le saute et on le signale
            skipped += 1
            print(f"  ! fichier ignoré {path.name} : {exc}")
    if not frames:
        print("Aucun fichier exploitable.")
        return

    df = clean(pd.concat(frames, ignore_index=True))
    if paris_day:
        df = df[df["date_paris"] == paris_day]
    print(f"{len(files)} fichiers bruts lus, {skipped} ignorés, {len(df)} lignes retenues")
    write_partitions(df, feed, data_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dossier des données (celui du collecteur)")
    parser.add_argument("--date", help="jour de Paris à traiter, AAAA-MM-JJ (par défaut : tous)")
    parser.add_argument("--feed", choices=[*FEEDS, "all"], default="all", help="flux à convertir (par défaut : tous)")
    args = parser.parse_args()

    for feed in FEEDS if args.feed == "all" else [args.feed]:
        convert(feed, Path(args.data), args.date)


if __name__ == "__main__":
    main()
