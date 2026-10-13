import numpy as np
import pandas as pd
import pytest

from evrel.features import MODEL_FEATURES
from evrel.monitoring.drift import psi, psi_level, psi_table
from evrel.monitoring.replay import (daily_performance, first_consecutive, nightly_lists,
                                     rolling_precision, silent_posts)


class FaultsScorer:
    """Faux modèle : score = pannes sur 7 jours."""

    def predict(self, df):
        return pd.DataFrame({"score": df["hw_faults_7d"].astype(float)}, index=df.index)


def nightly(n_posts=5, n_days=3, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2021-09-01", periods=n_days):
        for p in range(1, n_posts + 1):
            row = {c: 0.0 for c in MODEL_FEATURES}
            row.update(post_id=p, site="Park A", date=d, target_date=d + pd.Timedelta(days=1),
                       hw_faults_7d=float(p), y=float(rng.integers(0, 2)))
            rows.append(row)
    return pd.DataFrame(rows)


# --- Dérive (PSI) ---------------------------------------------------------------------------

def test_psi_is_zero_for_same_distribution_and_grows_with_the_shift():
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(0, 1, 5000))
    same, small, big = (pd.Series(rng.normal(m, 1, 5000)) for m in (0, 0.5, 1))
    assert psi(ref, same) < 0.02
    assert psi(ref, same) < psi(ref, small) < psi(ref, big)


def test_psi_sees_more_missing_values():
    ref = pd.Series(np.arange(1000.0))
    cur = ref.copy()
    cur[:300] = np.nan                       # 30 % de manques soudains
    assert psi(ref, cur) > 0.25


@pytest.mark.parametrize("value, level", [(0.05, "stable"), (0.15, "à surveiller"), (0.4, "dérive")])
def test_psi_levels(value, level):
    assert psi_level(value, warn=0.10, alert=0.25) == level


def test_psi_table_has_one_column_per_period():
    df = nightly(n_days=10)
    table = psi_table(df, df, df["date"].dt.day % 2, ["hw_faults_7d"])
    assert list(table.columns) == [0, 1] and list(table.index) == ["hw_faults_7d"]


# --- Rejeu ----------------------------------------------------------------------------------

def test_nightly_lists_rank_the_k_best_each_evening():
    journal = nightly_lists(nightly(), {"règle": FaultsScorer()}, k=2)
    assert journal.groupby("date").size().eq(2).all()
    assert journal.query("rank == 1")["post_id"].eq(5).all()      # la borne 5 a le plus de pannes


def test_an_evening_list_ignores_later_evenings():
    """Anti-fuite du rejeu : la liste du 1er septembre ne dépend pas de ce qui arrive le 2."""
    base = nightly()
    changed = base.copy()
    changed.loc[changed["date"] > "2021-09-01", "hw_faults_7d"] = 100.0
    first = lambda df: nightly_lists(df, {"règle": FaultsScorer()}, k=2).query("date == '2021-09-01'")
    pd.testing.assert_frame_equal(first(base).reset_index(drop=True), first(changed).reset_index(drop=True))


def test_unknown_labels_are_neither_hits_nor_misses():
    journal = pd.DataFrame({"target_date": pd.to_datetime(["2021-09-02"] * 3), "model": "m",
                            "post_id": [1, 2, 3], "y": [1.0, 0.0, np.nan]})
    perf = daily_performance(journal).iloc[0]
    assert (perf["listed"], perf["labelled"], perf["hits"]) == (3, 2, 1)
    assert rolling_precision(daily_performance(journal), 28).iloc[0, 0] == 0.5


def test_first_consecutive_waits_for_n_weeks():
    flags = pd.Series([False, True, False, True, True, True],
                      index=pd.date_range("2021-10-01", periods=6, freq="7D"))
    assert first_consecutive(flags, 2) == flags.index[4]
    assert first_consecutive(flags, 4) is None


def test_silent_posts_detects_a_stopped_post_only():
    days = pd.date_range("2021-09-01", "2021-09-30")
    sessions = pd.DataFrame({
        "post_id": [1] * 30 + [2] * 10,                         # borne 2 : plus rien après le 10 septembre
        "site": ["Park A"] * 40,
        "start_time": list(days) + list(days[:10]),
    })
    alerts = silent_posts(sessions, days, silent_days=7)
    assert alerts["post_id"].tolist() == [2]
    assert alerts["date"].iloc[0] == pd.Timestamp("2021-09-17")   # 7 jours sans recharge
