"""Nettoyage des sessions. Chaque règle est justifiée dans exploration/03_nettoyage.ipynb."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from evrel.data.load import FLAG_COLS, get_data_dir, load_config
from evrel.target import cause_family

# Colonnes retirées : connues après la session (fuite), ou redondantes avec l'énergie et le tarif.
LEAKY_COLS = ["paid_at", "amount_paid"]
REDUNDANT_COLS = ["amount", "electricity_cost", "service_charge", "order_created_at"]


def clean_sessions(raw: pd.DataFrame, start_date: str | None = None) -> pd.DataFrame:
    """Applique les règles de nettoyage et ajoute les colonnes dérivées utiles."""
    if start_date is None:
        start_date = load_config()["cleaning"]["start_date"]

    # Règle 1 : période d'étude (décembre 2019 exclu).
    df = raw[raw["start_time"] >= pd.Timestamp(start_date)].copy()

    # Règle 2 : sessions vides ou très courtes CONSERVÉES, mais repérées.
    df["duration_min"] = (df["end_time"] - df["start_time"]).dt.total_seconds() / 60
    df["is_empty"] = df["energy_kwh"].eq(0).astype("int8")
    df["is_short"] = df["duration_min"].lt(1).astype("int8")

    # Règle 3 : notre propre classement des causes remplace les indicateurs des auteurs.
    df["cause_family"] = cause_family(df["end_cause"])

    # Règle 4 : colonnes de fuite et redondantes retirées.
    df = df.drop(columns=LEAKY_COLS + REDUNDANT_COLS + FLAG_COLS)

    # Ordre chronologique par borne : indispensable pour tout calcul sur le passé.
    return df.sort_values(["post_id", "start_time"]).reset_index(drop=True)


def interim_path(name: str = "sessions.parquet") -> Path:
    return get_data_dir() / "interim" / name


def save_interim(df: pd.DataFrame, name: str = "sessions.parquet") -> Path:
    path = interim_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def load_interim(name: str = "sessions.parquet") -> pd.DataFrame:
    return pd.read_parquet(interim_path(name))