"""Baselines : des règles simples, sans apprentissage, que le modèle devra battre."""
from __future__ import annotations

import numpy as np
import pandas as pd


def baseline_scores(df: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Un score par règle : plus il est élevé, plus la borne est jugée à risque pour le lendemain."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Hasard": rng.random(len(df)),
        "Épisode aujourd'hui": df["episode_d0"],
        "Pannes sur 7 jours": df["hw_faults_7d"],
        "Épisode récent": -df["days_since_episode"],          # moins de jours = plus de risque
        "Taux historique": df["hist_hw_rate"].fillna(0),
    }, index=df.index)