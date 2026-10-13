"""Découpage temporel : chaque ligne est rangée selon la date du jour PRÉDIT."""
from __future__ import annotations

import pandas as pd

from evrel.data.load import load_config


def assign_split(target_dates: pd.Series, periods: dict | None = None) -> pd.Series:
    """Renvoie 'train', 'valid', 'test' ou 'replay' selon la période de la date prédite."""
    if periods is None:
        periods = load_config()["split"]
    out = pd.Series(pd.NA, index=target_dates.index, dtype="object")
    for name, (start, end) in periods.items():
        out[target_dates.between(pd.Timestamp(start), pd.Timestamp(end))] = name
    return out