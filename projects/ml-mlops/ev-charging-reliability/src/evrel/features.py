
"""Variables du modèle : ce que l'on sait le soir du jour J pour prédire un épisode le jour J+1.

Règle d'or : chaque variable de la ligne (borne, J) n'utilise que des sessions terminées au plus tard le jour J.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from evrel.data.load import load_config

WINDOWS = (3, 7, 28)

# Variables numériques retenues pour le modèle, regroupées par famille.
FEATURE_GROUPS = {
    "défauts récents": ["hw_faults_d0", "hw_faults_3d", "hw_faults_7d", "hw_faults_28d",
                        "hw_rate_7d", "hw_rate_28d", "hw_rate_trend", "hist_hw_rate"],
    "épisodes passés": ["episode_d0", "episodes_28d", "days_since_episode"],
    "signaux faibles": ["empty_share_7d", "short_share_7d", "vehicle_rate_7d"],
    "usage": ["sessions_d0", "sessions_7d", "sessions_28d", "usage_trend", "idle_days_7d", "post_age_days"],
    "calendrier": ["target_dow", "target_weekend", "target_month", "target_holiday"],
    "météo": ["temperature_c", "precipitation_mm", "humidity_pct"],
}
NUMERIC_FEATURES = [f for group in FEATURE_GROUPS.values() for f in group]
CATEGORICAL_FEATURES = ["site"]


def _daily_extras(sessions: pd.DataFrame) -> pd.DataFrame:
    """Comptes journaliers absents de la table cible : sessions vides, courtes, défauts véhicule."""
    df = sessions.assign(
        date=sessions["start_time"].dt.normalize(),
        is_vehicle=sessions["cause_family"].eq("Défaut véhicule").astype("int8"),
    )
    return (df.groupby(["post_id", "date"])
              .agg(n_empty=("is_empty", "sum"), n_short=("is_short", "sum"),
                   n_vehicle_faults=("is_vehicle", "sum"))
              .reset_index())


def _holiday_flags(dates: pd.Series, periods: list) -> pd.Series:
    flag = pd.Series(False, index=dates.index)
    for start, end in periods:
        flag |= dates.between(pd.Timestamp(start), pd.Timestamp(end))
    return flag.astype("int8")


def _rolling(g, col: str, window: int) -> pd.Series:
    """Somme glissante sur les `window` derniers jours, jour J INCLUS (connu le soir de J)."""
    return g[col].transform(lambda s: s.rolling(window, min_periods=1).sum())


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.where(den > 0)


def build_features(daily_target: pd.DataFrame, sessions: pd.DataFrame,
                   weather: pd.DataFrame, holidays: list | None = None, require_label: bool = True) -> pd.DataFrame:
    """Une ligne par borne et par jour J : variables connues le soir de J, cible = épisode en J+1."""
    if holidays is None:
        holidays = load_config()["calendar"]["holidays"]

    df = (daily_target.sort_values(["post_id", "date"])
          .merge(_daily_extras(sessions), on=["post_id", "date"], how="left")
          .reset_index(drop=True))
    for col in ["n_empty", "n_short", "n_vehicle_faults"]:
        df[col] = df[col].fillna(0)
    df["episode_d0"] = df["is_episode"].fillna(0)
    df["is_idle"] = df["n_sessions"].eq(0).astype("int8")
    g = df.groupby("post_id")

    # Cible : épisode le lendemain (la grille est complète, la ligne suivante est bien J+1).
    df["target_date"] = df["date"] + pd.Timedelta(days=1)
    df["y"] = g["is_episode"].shift(-1)

    # Défauts récents
    df["hw_faults_d0"] = df["n_hw_faults"]
    df["sessions_d0"] = df["n_sessions"]
    for w in WINDOWS:
        df[f"hw_faults_{w}d"] = _rolling(g, "n_hw_faults", w)
        df[f"sessions_{w}d"] = _rolling(g, "n_sessions", w)
    for col, name in [("n_empty", "empty_7d"), ("n_short", "short_7d"),
                      ("n_vehicle_faults", "vehicle_7d"), ("is_idle", "idle_days_7d")]:
        df[name] = _rolling(g, col, 7)
    df["episodes_28d"] = _rolling(g, "episode_d0", 28)

    df["hw_rate_7d"] = _safe_div(df["hw_faults_7d"], df["sessions_7d"])
    df["hw_rate_28d"] = _safe_div(df["hw_faults_28d"], df["sessions_28d"])
    df["hw_rate_trend"] = df["hw_rate_7d"] - df["hw_rate_28d"]
    df["hist_hw_rate"] = _safe_div(g["n_hw_faults"].cumsum(), g["n_sessions"].cumsum())

    # Signaux faibles : parts de sessions vides, très courtes, et défauts côté véhicule
    df["empty_share_7d"] = _safe_div(df["empty_7d"], df["sessions_7d"])
    df["short_share_7d"] = _safe_div(df["short_7d"], df["sessions_7d"])
    df["vehicle_rate_7d"] = _safe_div(df["vehicle_7d"], df["sessions_7d"])

    # Usage
    df["usage_trend"] = df["sessions_7d"] / 7 - df["sessions_28d"] / 28
    df["post_age_days"] = (df["date"] - g["date"].transform("min")).dt.days

    # Jours depuis le dernier épisode (365 si aucun épisode encore observé)
    last_episode = df["date"].where(df["episode_d0"].eq(1)).groupby(df["post_id"]).ffill()
    df["days_since_episode"] = (df["date"] - last_episode).dt.days.fillna(365).clip(upper=365)

    # Calendrier du jour PRÉDIT (connu à l'avance)
    df["target_date"] = df["date"] + pd.Timedelta(days=1)
    df["target_dow"] = df["target_date"].dt.dayofweek
    df["target_weekend"] = df["target_dow"].ge(5).astype("int8")
    df["target_month"] = df["target_date"].dt.month
    df["target_holiday"] = _holiday_flags(df["target_date"], holidays)

    # Météo observée le jour J dans le district de la borne
    district_of_post = sessions.groupby("post_id")["district"].first()
    df["district"] = df["post_id"].map(district_of_post)
    df = df.merge(weather[["district", "date", "temperature_c", "precipitation_mm", "humidity_pct"]],
                  on=["district", "date"], how="left")

    keys = ["post_id", "site", "district", "date", "target_date", "y"]
    out = df[keys + NUMERIC_FEATURES]
    return (out[out["y"].notna()] if require_label else out).reset_index(drop=True)

# Variables écartées (décision du notebook 05, prise sur la période d'entraînement uniquement).
DROPPED_FEATURES = {
    "vehicle_rate_7d": "AUC 0,506 : aucune information",
    "target_dow": "AUC 0,505 : épisodes de 6,4 à 7,5 % selon le jour, écart négligeable",
    "target_weekend": "AUC 0,499 : aucune information",
    "target_holiday": "AUC 0,501 : 7,25 % d'épisodes les jours fériés contre 7,02 %",
    "precipitation_mm": "AUC 0,512 : quasi aucune information",
    "humidity_pct": "AUC 0,507 : quasi aucune information",
    "target_month": "Une seule année d'entraînement : le mois se confond avec le temps qui passe",
    "post_age_days": "Corrélée à 0,996 avec le mois : mesure le temps, valeurs jamais vues en 2021",
}
MODEL_FEATURES = [f for f in NUMERIC_FEATURES if f not in DROPPED_FEATURES]