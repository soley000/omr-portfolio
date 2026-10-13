import numpy as np
import pandas as pd
import pytest

from evrel.features import MODEL_FEATURES
from evrel.models.compare import bootstrap_gain
from evrel.models.train import feature_columns, make_model


def make_days(n_days=30, n_posts=20, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "target_date": np.repeat(pd.date_range("2021-01-01", periods=n_days), n_posts),
        "y": rng.random(n_days * n_posts) < 0.2,
    }).astype({"y": int})
    df["parfait"] = df["y"] + rng.random(len(df)) * 0.1      # classe toujours les épisodes en premier
    df["baseline"] = rng.random(len(df))                      # classement au hasard
    return df


def test_identical_scores_give_zero_gain():
    g = bootstrap_gain(make_days(), "baseline", "baseline", k=5, n_boot=200)
    assert g["gain"] == 0 and g["ic_bas"] <= 0 <= g["ic_haut"]


def test_better_model_has_positive_interval():
    g = bootstrap_gain(make_days(), "parfait", "baseline", k=5, n_boot=200)
    assert g["ic_bas"] > 0


@pytest.mark.parametrize("kind", ["logreg", "hgb"])
@pytest.mark.parametrize("use_site", [False, True])
def test_models_train_and_predict(kind, use_site):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((200, len(MODEL_FEATURES))), columns=MODEL_FEATURES)
    X.iloc[0, 0] = np.nan                                     # une valeur manquante doit être gérée
    X["site"] = rng.choice(["Park A", "Bus Station"], 200)
    y = (rng.random(200) < 0.3).astype(int)
    model = make_model(kind, use_site).fit(X[feature_columns(use_site)], y)
    proba = model.predict_proba(X[feature_columns(use_site)])[:, 1]
    assert proba.shape == (200,) and ((proba >= 0) & (proba <= 1)).all()