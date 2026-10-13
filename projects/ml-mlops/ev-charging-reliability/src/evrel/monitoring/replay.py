"""Production simulée (rejeu) : chaque soir, la liste du lendemain ; chaque jour, les étiquettes de la veille."""
from __future__ import annotations

import numpy as np
import pandas as pd

from evrel.models.registry import as_model_input


def nightly_lists(nightly: pd.DataFrame, scorers: dict, k: int = 10, seed: int = 0) -> pd.DataFrame:
    """Journal de production : soir après soir, les k bornes choisies par chaque modèle.

    `nightly` : une ligne par borne et par soir (variables du soir J, cible y = épisode en J+1, inconnue le soir même).
    Les ex aequo sont départagés au hasard (graine fixe), comme dans l'évaluation.
    """
    rng = np.random.default_rng(seed)
    journal = []
    for evening, batch in nightly.groupby("date", sort=True):          # un soir à la fois, dans l'ordre
        X = as_model_input(batch)
        for name, scorer in scorers.items():
            scored = batch.assign(score=scorer.predict(X)["score"].to_numpy(), _tie=rng.random(len(batch)))
            top = scored.sort_values(["score", "_tie"], ascending=False).head(k)
            journal.append(top.assign(model=name, rank=np.arange(1, len(top) + 1),
                                      mean_score_all=scored["score"].mean(), n_posts=len(batch)))
    cols = ["date", "target_date", "model", "rank", "post_id", "site", "score", "y", "mean_score_all", "n_posts"]
    return pd.concat(journal, ignore_index=True)[cols]


def daily_performance(journal: pd.DataFrame) -> pd.DataFrame:
    """Le lendemain, on sait si les bornes signalées ont eu un épisode : succès par jour et par modèle.

    Une borne sans étiquette (aucune recharge le lendemain, ou niveau habituel inconnu) n'est comptée ni
    comme succès ni comme échec : on ne peut pas savoir.
    """
    j = journal.assign(known=journal["y"].notna(), hit=journal["y"].eq(1))
    return (j.groupby(["target_date", "model"])
             .agg(listed=("post_id", "size"), labelled=("known", "sum"), hits=("hit", "sum"))
             .reset_index())


def rolling_precision(perf: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Précision@k sur les `window_days` derniers jours connus, pour chaque modèle (colonnes)."""
    wide = perf.pivot(index="target_date", columns="model", values=["hits", "labelled"])
    rolled = wide.rolling(f"{window_days}D").sum()
    return rolled["hits"] / rolled["labelled"]


def weekly_checkpoints(rolling: pd.DataFrame, champion: str, fallback: str, window_days: int) -> pd.DataFrame:
    """Un contrôle par semaine, une fois la fenêtre remplie : le champion fait-il mieux que le repli ?"""
    start = rolling.index.min() + pd.Timedelta(days=window_days - 1)
    checks = rolling.loc[start:].iloc[::7].copy()
    checks["champion_behind"] = checks[champion] < checks[fallback]
    return checks


def first_consecutive(flags: pd.Series, n: int):
    """Date du n-ième contrôle consécutif à True (None si jamais) : on attend n semaines avant d'alerter."""
    run = flags.astype(int).groupby((~flags).cumsum()).cumsum()
    hit = run[run >= n]
    return None if hit.empty else hit.index[0]


def silent_posts(sessions: pd.DataFrame, evenings: pd.DatetimeIndex,
                 silent_days: int = 7, active_days: int = 28) -> pd.DataFrame:
    """Bornes devenues muettes : actives récemment, puis plus aucune recharge depuis `silent_days` jours.

    Un arrêt de borne n'est pas un épisode de pannes : le modèle ne le voit pas, la surveillance doit le voir.
    Renvoie la première alerte de chaque borne.
    """
    days = sessions["start_time"].dt.normalize()
    activity = (pd.crosstab(sessions["post_id"], days)
                  .reindex(columns=pd.date_range(days.min(), evenings.max(), freq="D"), fill_value=0))
    seen = np.where(activity.gt(0), activity.columns.values[None, :], np.datetime64("NaT"))
    last_seen = pd.DataFrame(seen, index=activity.index, columns=activity.columns).ffill(axis=1)  # dernière recharge connue
    alerts = []
    for evening in evenings:
        last = last_seen[evening]
        idle = (evening - last).dt.days
        mask = idle.ge(silent_days) & idle.lt(silent_days + active_days)
        alerts += [{"date": evening, "post_id": p, "last_session": last[p]} for p in last.index[mask]]
    out = pd.DataFrame(alerts, columns=["date", "post_id", "last_session"])
    site = sessions.groupby("post_id")["site"].first()
    return (out.groupby("post_id", as_index=False).first()
               .assign(site=lambda d: d["post_id"].map(site))
               .sort_values("date").reset_index(drop=True))
