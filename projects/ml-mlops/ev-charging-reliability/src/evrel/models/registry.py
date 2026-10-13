"""Registre des modèles (MLflow Model Registry) : versions numérotées et alias champion / fallback."""
from __future__ import annotations

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient

from evrel.features import MODEL_FEATURES

MODEL_NAME = "chargetriage"
INPUT_COLUMNS = MODEL_FEATURES + ["site"]      # ce que reçoit tout modèle enregistré, quel qu'il soit


class SklearnScorer(mlflow.pyfunc.PythonModel):
    """Emballe un pipeline scikit-learn : renvoie la probabilité d'épisode dans une colonne « score »."""

    def __init__(self, pipeline, columns: list[str]):
        self.pipeline = pipeline
        self.columns = columns

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        proba = self.pipeline.predict_proba(model_input[self.columns])[:, 1]
        return pd.DataFrame({"score": proba}, index=model_input.index)


class RuleScorer(mlflow.pyfunc.PythonModel):
    """La règle du bon sens, emballée comme un modèle : score = pannes matérielles sur 7 jours."""

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        return pd.DataFrame({"score": model_input["hw_faults_7d"].astype(float)}, index=model_input.index)


def as_model_input(df: pd.DataFrame) -> pd.DataFrame:
    """Colonnes attendues par les modèles enregistrés ; nombres en décimaux pour accepter les manques."""
    out = df[INPUT_COLUMNS].copy()
    out[MODEL_FEATURES] = out[MODEL_FEATURES].astype("float64")
    return out


def find_run(stage: str, kind: str) -> str:
    """Identifiant du run MLflow portant l'étiquette `stage` pour un type de modèle donné."""
    runs = mlflow.search_runs(filter_string=f"tags.stage = '{stage}' and params.kind = '{kind}'",
                              order_by=["start_time DESC"])
    if runs.empty:
        raise LookupError(f"Aucun run avec stage={stage} et kind={kind}")
    return runs.iloc[0]["run_id"]


def register(python_model: mlflow.pyfunc.PythonModel, alias: str, description: str,
             input_example: pd.DataFrame, source_run_id: str | None = None) -> str:
    """Enregistre un modèle dans le registre, lui donne un alias et une description. Renvoie la version."""
    tags = {"stage": "registry", "alias": alias}
    if source_run_id:
        tags["source_run_id"] = source_run_id
    with mlflow.start_run(run_name=f"Registre · {alias}", tags=tags):
        info = mlflow.pyfunc.log_model(name="model", python_model=python_model,
                                       input_example=input_example, registered_model_name=MODEL_NAME)
    version = str(info.registered_model_version)
    client = MlflowClient()
    client.set_registered_model_alias(MODEL_NAME, alias, version)
    client.update_model_version(MODEL_NAME, version, description=description)
    return version


def load_scorer(alias: str = "champion") -> mlflow.pyfunc.PyFuncModel:
    """Charge le modèle qui porte cet alias, sans savoir de quel fichier ni de quelle version il s'agit."""
    return mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{alias}")