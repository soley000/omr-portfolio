"""Évaluation d'un classement de bornes : la métrique métier est la liste des k bornes signalées chaque soir."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


def top_k_rows(df: pd.DataFrame, score_col: str, k: int, seed: int = 0) -> pd.DataFrame:
    """Les k bornes les mieux classées de chaque jour prédit.

    Les ex aequo sont départagés au hasard (graine fixe), comme le ferait un exploitant sans autre information.
    """
    rng = np.random.default_rng(seed)
    ranked = (df.assign(_tie=rng.random(len(df)))
                .sort_values(["target_date", score_col, "_tie"], ascending=[True, False, False]))
    return ranked.groupby("target_date").head(k).drop(columns="_tie")


def top_k_table(df: pd.DataFrame, score_col: str, k: int, seed: int = 0) -> pd.DataFrame:
    """Pour chaque jour prédit : bornes signalées, épisodes parmi elles, et épisodes au total."""
    top = top_k_rows(df, score_col, k, seed)
    return pd.DataFrame({
        "signalées": top.groupby("target_date").size(),
        "épisodes_signalés": top.groupby("target_date")["y"].sum(),
        "épisodes_total": df.groupby("target_date")["y"].sum(),
    })


def evaluate_ranking(df: pd.DataFrame, score_col: str, ks=(5, 10), seed: int = 0) -> dict:
    """Métriques métier (précision et rappel dans le top k) et métriques globales (AUC, PR-AUC)."""
    out = {}
    for k in ks:
        t = top_k_table(df, score_col, k, seed)
        out[f"précision@{k}"] = t["épisodes_signalés"].sum() / t["signalées"].sum()
        out[f"rappel@{k}"] = t["épisodes_signalés"].sum() / max(t["épisodes_total"].sum(), 1)
    score = df[score_col].fillna(df[score_col].min())
    out["AUC"] = roc_auc_score(df["y"], score)
    out["PR-AUC"] = average_precision_score(df["y"], score)
    out["taux de base"] = df["y"].mean()
    return out