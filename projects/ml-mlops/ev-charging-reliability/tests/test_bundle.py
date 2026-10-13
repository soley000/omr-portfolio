import json

import mlflow
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api.main import create_app
from evrel.features import MODEL_FEATURES
from evrel.models.bundle import (FEATURES_FILE, INFO_FILE, MODEL_DIR, docker_requirements,
                                 export_bundle, load_bundle)
from evrel.models.registry import RuleScorer, as_model_input, register


def fake_features(n=6):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.integers(0, 5, (n, len(MODEL_FEATURES))).astype(float), columns=MODEL_FEATURES)
    df["post_id"], df["site"] = range(1, n + 1), "Park A"
    df["date"], df["target_date"] = pd.Timestamp("2021-08-14"), pd.Timestamp("2021-08-15")
    df["y"], df["split"] = 0.0, "test"
    return df


def make_bundle(tmp_path):
    """Registre jetable avec une règle en champion, puis export du paquet."""
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    mlflow.create_experiment("test", artifact_location=(tmp_path / "artifacts").as_uri())
    mlflow.set_experiment("test")
    feats = fake_features()
    register(RuleScorer(), "champion", "règle", as_model_input(feats.head(3)))
    return feats, export_bundle(feats, tmp_path / "bundle")


def test_bundle_is_self_contained_and_has_no_target(tmp_path):
    feats, info = make_bundle(tmp_path)
    bundle = tmp_path / "bundle"
    assert (bundle / MODEL_DIR / "MLmodel").exists()
    assert json.loads((bundle / INFO_FILE).read_text())["model_version"] == info["model_version"] == "1"
    saved = pd.read_parquet(bundle / FEATURES_FILE)
    assert "y" not in saved.columns and "split" not in saved.columns   # la réponse ne part jamais en production

    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'autre.db').as_posix()}")   # registre vide : inutile ici
    model, info2, saved2 = load_bundle(bundle)
    assert (model.predict(as_model_input(saved2))["score"] == feats["hw_faults_7d"]).all()


def test_docker_requirements_are_pinned_and_light(tmp_path):
    make_bundle(tmp_path)
    reqs = docker_requirements(tmp_path / "bundle" / MODEL_DIR)
    assert all("==" in r for r in reqs)                       # versions exactes, pas de surprise
    assert any(r.startswith("mlflow-skinny==") for r in reqs)
    assert not any(r.startswith("mlflow==") for r in reqs)
    assert any(r.startswith("fastapi==") for r in reqs)


def test_api_serves_the_bundle(tmp_path, monkeypatch):
    make_bundle(tmp_path)
    monkeypatch.setenv("EVREL_BUNDLE_DIR", str(tmp_path / "bundle"))
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["model_version"] == "1"
        assert len(client.get("/ranking", params={"date": "2021-08-15", "k": 3}).json()["posts"]) == 3

def test_docker_requirements_skip_our_own_package_and_duplicates(tmp_path):
    (tmp_path / "requirements.txt").write_text("mlflow==3.17.0\nevrel==0.1.0\npyarrow==25.0.1\n")
    reqs = docker_requirements(tmp_path)
    assert not any(r.startswith("evrel") for r in reqs)       # pas sur PyPI : installé depuis src/
    assert len(reqs) == len(set(reqs))