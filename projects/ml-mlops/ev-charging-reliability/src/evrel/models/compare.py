"""Comparer un modèle à la baseline : gain, incertitude (bootstrap) et stabilité mois par mois."""
from __future__ import annotations

import numpy as np
import pandas as pd

from evrel.models.evaluate import top_k_table


def bootstrap_gain(df: pd.DataFrame, model_col: str, base_col: str, k: int = 10,
                   n_boot: int = 1000, confidence: float = 0.95, seed: int = 0) -> dict:
    """Gain de précision@k (modèle − baseline) et son intervalle de confiance, en rééchantillonnant les soirs."""
    tm = top_k_table(df, model_col, k)
    tb = top_k_table(df, base_col, k).loc[tm.index]
    hits_m, n_m = tm["épisodes_signalés"].to_numpy(), tm["signalées"].to_numpy()
    hits_b, n_b = tb["épisodes_signalés"].to_numpy(), tb["signalées"].to_numpy()

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(tm), size=(n_boot, len(tm)))      # n_boot tirages de soirs, avec remise
    gains = hits_m[idx].sum(1) / n_m[idx].sum(1) - hits_b[idx].sum(1) / n_b[idx].sum(1)

    alpha = (1 - confidence) / 2
    return {
        "gain": hits_m.sum() / n_m.sum() - hits_b.sum() / n_b.sum(),
        "ic_bas": float(np.quantile(gains, alpha)),
        "ic_haut": float(np.quantile(gains, 1 - alpha)),
    }


def monthly_precision(df: pd.DataFrame, cols: list[str], k: int = 10) -> pd.DataFrame:
    """Précision@k par mois pour plusieurs scores."""
    out = {}
    for col in cols:
        t = top_k_table(df, col, k)
        m = t.groupby(t.index.to_period("M")).sum()
        out[col] = m["épisodes_signalés"] / m["signalées"]
    return pd.DataFrame(out)


def decision(df: pd.DataFrame, model_col: str, base_col: str, min_gain: float = 0.03,
             k: int = 10, n_boot: int = 1000, confidence: float = 0.95) -> dict:
    """Applique la règle de décision fixée avant l'entraînement (notebook 06)."""
    g = bootstrap_gain(df, model_col, base_col, k, n_boot, confidence)
    months = monthly_precision(df, [model_col, base_col], k)
    return {
        **g,
        "c1_gain_suffisant": g["gain"] >= min_gain,
        "c2_gain_significatif": g["ic_bas"] > 0,
        "c3_aucun_mois_perdant": bool((months[model_col] >= months[base_col]).all()),
        "retenu": g["gain"] >= min_gain and g["ic_bas"] > 0
                  and bool((months[model_col] >= months[base_col]).all()),
    }