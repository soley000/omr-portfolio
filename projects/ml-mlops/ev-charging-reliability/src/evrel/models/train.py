"""Modèles candidats et suivi des expériences avec MLflow."""
from __future__ import annotations

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from evrel.data.load import get_data_dir, load_config
from evrel.features import MODEL_FEATURES
from evrel.models.compare import decision
from evrel.models.evaluate import evaluate_ranking

BASELINE = "Pannes sur 7 jours"


def setup_mlflow(experiment: str = "chargetriage") -> None:
    """Base MLflow locale (SQLite) et artefacts rangés à côté des données, hors du dépôt."""
    root = get_data_dir() / "mlflow"
    root.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{(root / 'mlflow.db').as_posix()}")
    if mlflow.get_experiment_by_name(experiment) is None:
        mlflow.create_experiment(experiment, artifact_location=(root / "artifacts").as_uri())
    mlflow.set_experiment(experiment)


def feature_columns(use_site: bool) -> list[str]:
    return MODEL_FEATURES + (["site"] if use_site else [])


def make_model(kind: str, use_site: bool = False, **params) -> Pipeline:
    """Préparation des colonnes + algorithme, dans un seul objet (Pipeline)."""
    if kind == "logreg":
        numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
        algo = LogisticRegression(max_iter=2000, **params)
    elif kind == "hgb":
        numeric = "passthrough"                              # le gradient boosting gère les manquants
        algo = HistGradientBoostingClassifier(random_state=0, **params)
    else:
        raise ValueError(f"Modèle inconnu : {kind}")
    parts = [("num", numeric, MODEL_FEATURES)]
    if use_site:
        parts.append(("site", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["site"]))
    return Pipeline([("prep", ColumnTransformer(parts)), ("algo", algo)])


def _metric_name(name: str) -> str:
    """MLflow n'accepte que des noms simples : 'précision@10' -> 'precision_at_10'."""
    return (name.replace("précision", "precision").replace("rappel", "recall")
                .replace("@", "_at_").replace(" ", "_").replace("-", "_"))


def run_experiment(train: pd.DataFrame, valid: pd.DataFrame, kind: str, use_site: bool = False,
                   run_name: str | None = None, tags: dict | None = None, **params) -> tuple[dict, pd.Series]:
    """Entraîne sur `train`, évalue sur `valid`, enregistre tout dans MLflow. Renvoie les métriques et les scores.

    `valid` est la période évaluée : la validation pendant la sélection, le test pour l'évaluation finale.
    """
    cfg = load_config()["evaluation"]
    cols = feature_columns(use_site)
    model = make_model(kind, use_site, **params)

    with mlflow.start_run(run_name=run_name, tags=tags):
        model.fit(train[cols], train["y"])
        scores = pd.Series(model.predict_proba(valid[cols])[:, 1], index=valid.index, name="score")
        scored = valid.assign(score=scores)

        metrics = evaluate_ranking(scored, "score", tuple(cfg["top_k"]))
        metrics["brier"] = brier_score_loss(valid["y"], scores)
        metrics["mean_predicted"] = scores.mean()
        dec = decision(scored, "score", BASELINE, min_gain=cfg["decision"]["min_gain"],
                       n_boot=cfg["decision"]["n_boot"], confidence=cfg["decision"]["confidence"])
        metrics.update({k: float(v) for k, v in dec.items()})

        mlflow.log_params({"kind": kind, "use_site": use_site, "n_features": len(cols), **params})
        mlflow.log_metrics({_metric_name(k): float(v) for k, v in metrics.items()})
        mlflow.sklearn.log_model(model, name="model", input_example=valid[cols].head(5),
                                 serialization_format="cloudpickle")

    return metrics, scores


def log_baseline(df: pd.DataFrame, run_name: str, tags: dict | None = None) -> dict:
    """Enregistre dans MLflow les métriques de la règle du bon sens sur une période (aucun entraînement)."""
    cfg = load_config()["evaluation"]
    metrics = evaluate_ranking(df, BASELINE, tuple(cfg["top_k"]))
    with mlflow.start_run(run_name=run_name, tags=tags):
        mlflow.log_params({"kind": "rule", "rule": BASELINE})
        mlflow.log_metrics({_metric_name(k): float(v) for k, v in metrics.items()})
    return metrics