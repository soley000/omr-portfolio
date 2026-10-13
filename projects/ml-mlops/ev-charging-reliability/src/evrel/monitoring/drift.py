"""Dérive des données : les variables d'aujourd'hui ressemblent-elles à celles sur lesquelles le modèle a appris ?"""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-4   # évite log(0) quand une case est vide d'un côté


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Population Stability Index.

    On découpe la référence en `bins` cases de même effectif (déciles), on compte la part de chaque
    période dans chaque case, puis PSI = somme de (actuel - référence) x ln(actuel / référence).
    Les valeurs manquantes forment une case à part : une hausse des manques est aussi une dérive.
    """
    ref, cur = reference.astype(float), current.astype(float)
    edges = np.unique(np.nanquantile(ref, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf

    def shares(x: pd.Series) -> np.ndarray:
        counts = pd.cut(x.dropna(), edges, include_lowest=True).value_counts(sort=False).to_numpy()
        counts = np.append(counts, x.isna().sum())
        return np.clip(counts / max(len(x), 1), EPS, None)

    r, c = shares(ref), shares(cur)
    return float(np.sum((c - r) * np.log(c / r)))


def psi_level(value: float, warn: float, alert: float) -> str:
    return "dérive" if value >= alert else "à surveiller" if value >= warn else "stable"


def psi_table(reference: pd.DataFrame, current: pd.DataFrame, period: pd.Series,
              features: list[str], bins: int = 10) -> pd.DataFrame:
    """PSI de chaque variable (lignes) pour chaque période de `current` (colonnes, ex. le mois)."""
    return pd.DataFrame({
        p: {f: psi(reference[f], chunk[f], bins) for f in features}
        for p, chunk in current.groupby(period, sort=True)
    })
