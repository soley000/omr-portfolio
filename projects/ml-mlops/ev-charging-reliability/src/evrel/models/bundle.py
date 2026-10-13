"""Paquet de déploiement : le modèle champion et les variables, copiés dans un dossier autonome.

Le conteneur Docker ne voit ni la base MLflow ni le disque C: ; on lui fournit ce dossier.
Usage : python -m evrel.models.bundle   (crée <dossier des données>/bundle)
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from datetime import datetime, timezone
from importlib.metadata import version as installed_version
from pathlib import Path

import mlflow
import mlflow.pyfunc
import pandas as pd

from evrel.models.registry import MODEL_NAME

MODEL_DIR, FEATURES_FILE, INFO_FILE = "model", "features.parquet", "model_info.json"
API_PACKAGES = ["fastapi", "uvicorn", "pydantic", "pyarrow", "PyYAML"]   # en plus de ce que le modèle exige
LOCAL_PACKAGES = {"evrel"}   # notre propre code : installé depuis src/ dans l'image, absent de PyPI


def _force_remove(func, path, _exc_info):
    """Windows refuse de supprimer un fichier en lecture seule : on lève la protection puis on réessaie."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def export_bundle(features: pd.DataFrame, dst: Path, alias: str = "champion") -> dict:
    """Copie le modèle qui porte `alias` et les variables (sans la cible) dans `dst`."""
    from mlflow import MlflowClient

    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst, onerror=_force_remove)    # un paquet se reconstruit en entier, jamais à moitié
    dst.mkdir(parents=True)
    version = MlflowClient().get_model_version_by_alias(MODEL_NAME, alias)
    mlflow.artifacts.download_artifacts(f"models:/{MODEL_NAME}@{alias}", dst_path=str(dst / MODEL_DIR))
    features.drop(columns=["y", "split"], errors="ignore").to_parquet(dst / FEATURES_FILE, index=False)
    info = {"model_name": MODEL_NAME, "alias": alias, "model_version": str(version.version),
            "run_id": version.run_id, "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (dst / INFO_FILE).write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def docker_requirements(model_dir: Path) -> list[str]:
    """Versions exactes pour l'image : celles notées par MLflow pour le modèle, plus celles de l'API.
    mlflow-skinny suffit pour charger un modèle (pas d'interface ni de serveur de suivi)."""
    lines = (Path(model_dir) / "requirements.txt").read_text(encoding="utf-8").split()
    lines = [line.replace("mlflow==", "mlflow-skinny==") for line in lines
             if line.strip() and line.split("==")[0].lower() not in LOCAL_PACKAGES]
    return list(dict.fromkeys(lines + [f"{p}=={installed_version(p)}" for p in API_PACKAGES]))   # sans doublons


def model_python_version(model_dir: Path) -> str:
    """Version de Python avec laquelle le modèle a été enregistré (fichier python_env.yaml)."""
    import yaml
    env = yaml.safe_load((Path(model_dir) / "python_env.yaml").read_text(encoding="utf-8"))
    return str(env["python"])


def load_bundle(src: Path):
    """Renvoie (modèle, informations, variables) depuis un paquet, sans base MLflow."""
    src = Path(src)
    info = json.loads((src / INFO_FILE).read_text(encoding="utf-8"))
    return mlflow.pyfunc.load_model(str(src / MODEL_DIR)), info, pd.read_parquet(src / FEATURES_FILE)


if __name__ == "__main__":
    from evrel.data.load import PROJECT_ROOT, get_data_dir
    from evrel.models.train import setup_mlflow

    setup_mlflow()
    bundle_dir = get_data_dir() / "bundle"         # avec les données, hors OneDrive et hors Git
    feats = pd.read_parquet(get_data_dir() / "processed" / "features.parquet")
    info = export_bundle(feats, bundle_dir)
    print(f"Paquet créé dans {bundle_dir} : {info['model_name']} version {info['model_version']} "
          f"({info['alias']}), {len(feats):,} lignes de variables")

    reqs = docker_requirements(bundle_dir / MODEL_DIR)
    (PROJECT_ROOT / "requirements-docker.txt").write_text("\n".join(reqs) + "\n", encoding="utf-8")
    print("requirements-docker.txt :", ", ".join(reqs))
    print("Python du modèle :", model_python_version(bundle_dir / MODEL_DIR),
          "→ l'image Docker doit utiliser la même version mineure (ARG PYTHON_VERSION du Dockerfile)")