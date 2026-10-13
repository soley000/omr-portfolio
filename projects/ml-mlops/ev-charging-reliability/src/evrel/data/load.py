"""Lecture des fichiers bruts du jeu de données de Jiaxing."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yaml

# load.py -> data -> evrel -> src -> racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_data_dir() -> Path:
    """La variable EVREL_DATA_DIR est prioritaire, sinon config.yaml."""
    env = os.environ.get("EVREL_DATA_DIR")
    if env:
        return Path(env)
    return Path(load_config()["data_dir"])


COLUMNS = {
    "UserID": "user_id",
    "Charging Post ID": "post_id",
    "Location Information": "site",
    "District Name": "district",
    "Order creation time": "order_created_at",
    "Transaction power/kwh": "energy_kwh",
    "Electricity cost/Yuan": "electricity_cost",
    "Service charge/Yuan": "service_charge",
    "Transaction Amount/Yuan": "amount",
    "Actual Payment/Yuan": "amount_paid",
    "Start Time": "start_time",
    "End Time": "end_time",
    "Payment time": "paid_at",
    "Relative Humidity(%)": "humidity_pct",
    "Precipitation(mm)": "precipitation_mm",
}

DATETIME_COLS = ["order_created_at", "start_time", "end_time", "paid_at"]
TEXT_COLS = ["site", "district", "end_cause"]
FLAG_COLS = [
    "is_full_charge", "is_user_stop", "is_nonsystem_fault",
    "is_system_issue", "is_EV_fault", "is_other_fault", "is_abnormal",
]


def _rename(col: str) -> str:
    # le nom de la température contient le symbole °C, mal encodé selon les outils
    if col.startswith("Temperature"):
        return "temperature_c"
    return COLUMNS.get(col, col)


def load_sessions(path: Path | None = None) -> pd.DataFrame:
    """Charge les sessions brutes, avec des noms, des textes et des types propres."""
    if path is None:
        path = get_data_dir() / "raw" / "Dataset" / "Charging_Data.csv"

    df = pd.read_csv(path, encoding="gb18030")

    df.columns = [_rename(c.strip()) for c in df.columns]

    for col in TEXT_COLS:
        df[col] = df[col].str.strip()  # "Industrial Park\t" -> "Industrial Park"

    for col in DATETIME_COLS:
        df[col] = pd.to_datetime(df[col].str.strip(), format="%Y-%m-%d %H:%M:%S")

    df[FLAG_COLS] = df[FLAG_COLS].astype("int8")
    return df

def load_weather(path: Path | None = None) -> pd.DataFrame:
    """Météo journalière par district (une ligne par district et par jour)."""
    if path is None:
        path = get_data_dir() / "raw" / "Dataset" / "Weather_Data.csv"
    w = pd.read_csv(path, encoding="gb18030")
    w.columns = [_rename(c.strip()) for c in w.columns]     # Temperature(°C) -> temperature_c
    w = w.rename(columns={"District Name": "district", "Date": "date"})
    w["district"] = w["district"].str.strip()
    w["date"] = pd.to_datetime(w["date"].astype(str), format="%Y%m%d")
    # Le fichier source contient le 1er de chaque mois de 2021 en double (identiques) : on n'en garde qu'un.
    return w.drop_duplicates(["district", "date"]).reset_index(drop=True)