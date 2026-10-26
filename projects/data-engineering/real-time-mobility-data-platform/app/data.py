"""Accès aux données du tableau de bord.

Règle d'or : le tableau de bord ne calcule rien de "métier" lui-même et n'écrit jamais.
Il LIT les tables déjà construites et testées par dbt (dim_*, fct_*), en lecture seule.
Ce fichier ne dépend pas de Streamlit : il peut être testé seul.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd


def warehouse_path() -> Path:
    """Chemin du fichier DuckDB publié par Airflow (voir MOBILITYFLOW_WAREHOUSE_PATH / _DATA_DIR)."""
    explicit = os.environ.get("MOBILITYFLOW_WAREHOUSE_PATH")
    if explicit:
        return Path(explicit)
    data_dir = os.environ.get("MOBILITYFLOW_DATA_DIR", "C:/dev/mobilityflow-data")
    local = Path(data_dir) / "warehouse" / "mobilityflow.duckdb"
    if local.exists():
        return local
    # Pas de base locale (cas de l'hebergeur) : export fige publie avec le projet.
    return Path(__file__).resolve().parent.parent / "export" / "mobilityflow_frozen.duckdb"


def _read(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def _read_meta(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    """Chiffres de synthese : table export_meta dans l'export fige, sinon calcul sur la vraie base."""
    has_export = con.execute("select count(*) from information_schema.tables where table_name = 'export_meta'").fetchone()[0]
    return _read(con, "select * from export_meta") if has_export else _read(con, sql)


def load_warehouse(path: str) -> dict[str, pd.DataFrame]:
    """Charge toutes les tables utiles en une seule connexion LECTURE SEULE, courte.

    Connexion courte + lecture seule = on ne bloque jamais la publication de 3 h d'Airflow
    (DuckDB n'accepte qu'un seul écrivain à la fois).
    Les horodatages sont convertis en heure de Paris "sans fuseau" directement en SQL.
    """
    con = duckdb.connect(path, read_only=True)
    try:
        tables = {
            "stations": _read(con, """
                select station_id, name, address, lat, lon,
                       capacity_declared, capacity_observed, has_capacity_gap, is_in_service_now
                from dim_station"""),
            "hours": _read(con, """
                select station_id, date_paris, hour_paris, snapshots, snapshots_in_service,
                       avg_bikes, min_bikes, max_bikes, pct_empty, pct_full, avg_fill_rate
                from fct_station_hour"""),
            "collection": _read(con, """
                select date_paris, hour_paris, snapshots, expected_snapshots, missing_snapshots,
                       completeness, is_partial_hour
                from fct_collection_hourly"""),
            "unchanged": _read(con, """
                select station_id, longest_unchanged_minutes, current_unchanged_minutes, looks_frozen_now
                from fct_station_unchanged"""),
            "meta": _read_meta(con, """
                select count(*)                                                    as snapshots_rows,
                       count(distinct station_id)                                  as stations,
                       count(distinct date_paris)                                  as days,
                       min(date_paris)                                             as first_date,
                       max(date_paris)                                             as last_date,
                       cast(timezone('Europe/Paris', min(snapshot_ts)) as timestamp) as first_snapshot,
                       cast(timezone('Europe/Paris', max(snapshot_ts)) as timestamp) as last_snapshot
                from stg_station_status"""),
        }
    finally:
        con.close()
    return tables


# ---------- petites fonctions de calcul réutilisées par l'appli ----------

def weighted_rates(hours: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Taux moyens pondérés par le nombre de relevés où la station est en service.

    On ne fait jamais la moyenne de moyennes : une heure avec 60 relevés pèse plus qu'une
    heure avec 8 relevés.
    """
    d = hours.copy()
    w = d["snapshots_in_service"].fillna(0)
    d["_e"] = d["pct_empty"].fillna(0) * w
    d["_f"] = d["pct_full"].fillna(0) * w
    d["_fill"] = d["avg_fill_rate"].fillna(0) * w
    d["_w"] = w
    g = d.groupby(by, as_index=False).agg(e=("_e", "sum"), f=("_f", "sum"), fill=("_fill", "sum"), n=("_w", "sum"))
    n = g["n"].where(g["n"] > 0)
    g["pct_empty"] = g["e"] / n
    g["pct_full"] = g["f"] / n
    g["fill_rate"] = g["fill"] / n
    return g.drop(columns=["e", "f", "fill"]).rename(columns={"n": "snapshots_in_service"})


def fmt_pct(x: float, digits: int = 0) -> str:
    if x is None or pd.isna(x):
        return "n/d"
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def fmt_minutes(m) -> str:
    if m is None or pd.isna(m):
        return "n/d"
    m = int(round(m))
    return f"{m // 60} h {m % 60:02d}" if m >= 60 else f"{m} min"