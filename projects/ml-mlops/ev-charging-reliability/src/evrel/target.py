"""Construction de la cible : défauts matériels par borne et par jour."""
from __future__ import annotations

import pandas as pd

from evrel.data.load import load_config


def hardware_causes() -> list[str]:
    """Liste des causes de fin comptées comme défaut matériel (lue dans config.yaml)."""
    return list(load_config()["target"]["hardware_causes"])


def cause_family(end_cause: pd.Series) -> pd.Series:
    """Classe chaque cause de fin dans une famille : matériel, véhicule, ambiguë ou normale."""
    cfg = load_config()["target"]
    families = {c: "Défaut matériel" for c in cfg["hardware_causes"]}
    families |= {c: "Défaut véhicule" for c in cfg["excluded_vehicle_causes"]}
    families |= {c: "Ambiguë (exclue)" for c in cfg["excluded_ambiguous_causes"]}
    return end_cause.map(families).fillna("Fin normale")


def add_hardware_fault(sessions: pd.DataFrame, causes: list[str]) -> pd.DataFrame:
    """Ajoute is_hw_fault = 1 quand la session s'est terminée par un défaut matériel."""
    out = sessions.copy()
    out["is_hw_fault"] = out["end_cause"].isin(causes).astype("int8")
    return out


def daily_post_table(sessions: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par borne et par jour, jours sans session compris."""
    df = sessions.assign(date=sessions["start_time"].dt.normalize())

    daily = (
        df.groupby(["post_id", "date"])
        .agg(
            n_sessions=("start_time", "size"),
            n_hw_faults=("is_hw_fault", "sum"),
            energy_kwh=("energy_kwh", "sum"),
        )
        .reset_index()
    )

    # Grille complète : chaque jour entre la première et la dernière session de la borne.
    spans = daily.groupby("post_id")["date"].agg(["min", "max"])
    grid = pd.concat(
        [
            pd.DataFrame({"post_id": post, "date": pd.date_range(row["min"], row["max"], freq="D")})
            for post, row in spans.iterrows()
        ],
        ignore_index=True,
    )
    daily = grid.merge(daily, on=["post_id", "date"], how="left")

    for col in ["n_sessions", "n_hw_faults"]:
        daily[col] = daily[col].fillna(0).astype("int32")
    daily["energy_kwh"] = daily["energy_kwh"].fillna(0.0)

    site_of_post = sessions.groupby("post_id")["site"].first()
    daily["site"] = daily["post_id"].map(site_of_post)

    # Taux du jour : indéfini (NaN) quand la borne n'a eu aucune session.
    daily["hw_fault_rate"] = daily["n_hw_faults"] / daily["n_sessions"].where(daily["n_sessions"] > 0)
    return daily


def add_past_baseline(daily: pd.DataFrame, window: int = 28) -> pd.DataFrame:
    """Niveau habituel de chaque borne, calculé uniquement sur les jours PASSÉS.

    baseline_rate = défauts / sessions sur les `window` jours précédents (jour J exclu).
    """
    out = daily.sort_values(["post_id", "date"]).copy()
    g = out.groupby("post_id")
    past_faults = g["n_hw_faults"].transform(lambda s: s.shift(1).rolling(window, min_periods=7).sum())
    past_sessions = g["n_sessions"].transform(lambda s: s.shift(1).rolling(window, min_periods=7).sum())
    out["baseline_rate"] = past_faults / past_sessions.where(past_sessions > 0)
    return out

def label_episodes(daily: pd.DataFrame, min_faults: int, min_ratio: float | None = None) -> pd.DataFrame:
    """Ajoute is_episode : 1 si le jour est un épisode anormal, 0 sinon, NaN si non observable.

    Épisode = au moins `min_faults` défauts matériels dans la journée et, si `min_ratio` est donné,
    un taux de défauts au moins `min_ratio` fois supérieur au niveau habituel de la borne.
    Non observable (NaN) : jour sans session, ou niveau habituel encore inconnu.
    """
    out = daily.copy()
    label = out["n_hw_faults"] >= min_faults
    if min_ratio is not None:
        ratio = out["hw_fault_rate"] / out["baseline_rate"]   # niveau habituel nul -> ratio infini
        label &= ratio >= min_ratio
    out["is_episode"] = label.astype("float")
    if min_ratio is not None:
        out.loc[out["baseline_rate"].isna(), "is_episode"] = float("nan")
    out.loc[out["n_sessions"] == 0, "is_episode"] = float("nan")
    return out