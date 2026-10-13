import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import EXAMPLE_POST
from evrel.features import MODEL_FEATURES


class FakeScorer:
    """Remplace le modèle du registre : score = pannes sur 7 jours. Le test ne dépend pas de MLflow."""

    def predict(self, df):
        return pd.DataFrame({"score": df["hw_faults_7d"].astype(float)}, index=df.index)


def fake_features():
    """3 bornes sur 2 soirs, avec des pannes connues pour vérifier l'ordre de la liste."""
    rows = []
    for day, faults in [("2021-08-14", [1, 5, 3]), ("2021-08-15", [0, 2, 2])]:
        for post, f in zip([10, 20, 30], faults):
            row = {c: 0.0 for c in MODEL_FEATURES}
            row.update(post_id=post, site="Park A", hw_faults_7d=float(f),
                       date=pd.Timestamp(day), target_date=pd.Timestamp(day) + pd.Timedelta(days=1))
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture
def client():
    app = create_app(scorer=FakeScorer(), model_version="7", features=fake_features())
    with TestClient(app) as c:          # « with » déclenche le démarrage (lifespan)
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["model_version"] == "7" and body["alias"] == "champion"
    assert body["first_inspection_date"] == "2021-08-15"


def test_predict_returns_one_score_per_post(client):
    missing = {**EXAMPLE_POST, "hw_rate_7d": None, "temperature_c": None}   # les manques sont acceptés
    r = client.post("/predict", json={"posts": [EXAMPLE_POST, missing]})
    assert r.status_code == 200
    assert r.json()["scores"] == [EXAMPLE_POST["hw_faults_7d"]] * 2


@pytest.mark.parametrize("change", [
    {"hw_faults_7d": -1},          # un nombre de pannes négatif n'a pas de sens
    {"hw_rate_7d": 1.5},           # un taux est entre 0 et 1
    {"unknown_column": 3},         # une variable que le modèle ne connaît pas
])
def test_predict_rejects_invalid_input(client, change):
    r = client.post("/predict", json={"posts": [{**EXAMPLE_POST, **change}]})
    assert r.status_code == 422


def test_predict_rejects_missing_variable(client):
    incomplete = {k: v for k, v in EXAMPLE_POST.items() if k != "hw_faults_7d"}
    assert client.post("/predict", json={"posts": [incomplete]}).status_code == 422


def test_ranking_orders_posts_and_uses_the_evening_before(client):
    body = client.get("/ranking", params={"date": "2021-08-15", "k": 2}).json()
    assert body["features_date"] == "2021-08-14"
    assert [p["post_id"] for p in body["posts"]] == [20, 30]
    assert [p["rank"] for p in body["posts"]] == [1, 2]


def test_ranking_ties_are_broken_by_post_id(client):
    body = client.get("/ranking", params={"date": "2021-08-16", "k": 2}).json()
    assert [p["post_id"] for p in body["posts"]] == [20, 30]


def test_ranking_errors(client):
    assert client.get("/ranking", params={"date": "2030-01-01"}).status_code == 404
    assert client.get("/ranking", params={"date": "15/08/2021"}).status_code == 422
    assert client.get("/ranking", params={"date": "2021-08-15", "k": 0}).status_code == 422

def test_liste_is_a_readable_french_page(client):
    r = client.get("/liste", params={"date": "2021-08-15", "k": 2})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Bornes à inspecter le dimanche 15 août 2021" in r.text
    assert r.text.index("Borne 20") < r.text.index("Borne 30")      # même ordre que /ranking


def test_liste_defaults_to_last_date_and_explains_errors(client):
    assert "lundi 16 août 2021" in client.get("/liste").text
    r = client.get("/liste", params={"date": "2030-01-01"})
    assert r.status_code == 404 and "Aucune variable calculée" in r.text


def test_liste_shows_counts_not_percentages_with_the_fallback_rule():
    app = create_app(scorer=FakeScorer(), features=fake_features())   # FakeScorer = la règle : scores > 1
    with TestClient(app) as c:
        text = c.get("/liste", params={"date": "2021-08-15"}).text
    assert "Score (règle de repli)" in text and "500" not in text

def test_home_redirects_to_liste(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/liste"