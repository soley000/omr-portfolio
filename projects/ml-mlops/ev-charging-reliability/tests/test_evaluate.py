import pandas as pd
import pytest

from evrel.models.baselines import baseline_scores
from evrel.models.evaluate import evaluate_ranking, top_k_table


def make_days():
    """Deux jours, 4 bornes chacun. Jour 1 : les 2 épisodes sont les mieux classés. Jour 2 : un seul sur deux."""
    return pd.DataFrame({
        "target_date": pd.to_datetime(["2021-01-01"] * 4 + ["2021-01-02"] * 4),
        "score":       [0.9, 0.8, 0.2, 0.1,   0.9, 0.8, 0.2, 0.1],
        "y":           [1,   1,   0,   0,     1,   0,   0,   1],
    })


def test_top_k_counts_per_day():
    t = top_k_table(make_days(), "score", k=2)
    assert t["épisodes_signalés"].tolist() == [2, 1]
    assert t["épisodes_total"].tolist() == [2, 2]


def test_precision_and_recall_at_k():
    m = evaluate_ranking(make_days(), "score", ks=(2,))
    assert m["précision@2"] == pytest.approx(3 / 4)      # 3 bons signalements sur 4 bornes signalées
    assert m["rappel@2"] == pytest.approx(3 / 4)         # 3 épisodes captés sur 4


def test_baselines_rank_risk_upwards():
    df = pd.DataFrame({"episode_d0": [1, 0], "hw_faults_7d": [5, 0],
                       "days_since_episode": [0, 100], "hist_hw_rate": [0.2, 0.05]})
    s = baseline_scores(df)
    for rule in ["Épisode aujourd'hui", "Pannes sur 7 jours", "Épisode récent", "Taux historique"]:
        assert s.loc[0, rule] > s.loc[1, rule]           # la borne 0 est la plus à risque