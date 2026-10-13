import mlflow
import numpy as np
import pandas as pd

from evrel.features import MODEL_FEATURES
from evrel.models.registry import (INPUT_COLUMNS, MODEL_NAME, RuleScorer, SklearnScorer,
                                   as_model_input, load_scorer, register)
from evrel.models.train import feature_columns, make_model


def fake_rows(n=50, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(rng.integers(0, 5, (n, len(MODEL_FEATURES))), columns=MODEL_FEATURES)
    df["site"] = rng.choice(["Park A", "Bus Station"], n)
    return df


def use_temporary_mlflow(tmp_path):
    """Un registre MLflow jetable, dans un dossier temporaire : le test ne touche pas au vrai registre."""
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    mlflow.create_experiment("test", artifact_location=(tmp_path / "artifacts").as_uri())
    mlflow.set_experiment("test")


def test_register_and_load_by_alias(tmp_path):
    use_temporary_mlflow(tmp_path)
    rows = fake_rows()
    y = (rows["hw_faults_7d"] > 2).astype(int)
    pipeline = make_model("hgb", use_site=True, max_iter=20).fit(rows[feature_columns(True)], y)

    v_rule = register(RuleScorer(), "fallback", "règle", as_model_input(rows.head(3)))
    v_model = register(SklearnScorer(pipeline, feature_columns(True)), "champion", "boosting",
                       as_model_input(rows.head(3)))
    assert (v_rule, v_model) == ("1", "2")                 # deux versions du même modèle enregistré

    champion = load_scorer("champion").predict(as_model_input(rows))
    fallback = load_scorer("fallback").predict(as_model_input(rows))
    assert list(champion.columns) == ["score"] and champion["score"].between(0, 1).all()
    assert (fallback["score"] == rows["hw_faults_7d"]).all()


def test_model_input_has_expected_columns():
    out = as_model_input(fake_rows(5))
    assert list(out.columns) == INPUT_COLUMNS
    assert (out[MODEL_FEATURES].dtypes == "float64").all()  # les manques resteront acceptés par le schéma