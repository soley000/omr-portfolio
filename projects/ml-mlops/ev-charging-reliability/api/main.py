"""API ChargeTriage : sert la liste des bornes à inspecter, avec le modèle qui porte l'alias champion."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date

import pandas as pd
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.page import error_page, ranking_page
from api.schemas import (HealthResponse, PredictRequest, PredictResponse, RankedPost,
                         RankingResponse)
from evrel.data.load import get_data_dir
from evrel.models.registry import MODEL_NAME, as_model_input

MACHINES = "Pour les logiciels (réponses JSON)"
HUMAINS = "Pour les humains (page web)"

router = APIRouter()


def load_features() -> pd.DataFrame:
    """Variables déjà calculées, une ligne par borne et par soir. La cible y n'a rien à faire ici."""
    feats = pd.read_parquet(get_data_dir() / "processed" / "features.parquet")
    return feats.drop(columns=["y", "split"], errors="ignore")


def load_champion(alias: str):
    """Charge le modèle par son alias dans le registre MLflow et renvoie aussi son numéro de version."""
    from mlflow import MlflowClient

    from evrel.models.registry import load_scorer
    from evrel.models.train import setup_mlflow

    setup_mlflow()
    version = MlflowClient().get_model_version_by_alias(MODEL_NAME, alias).version
    return load_scorer(alias), str(version)


def create_app(scorer=None, model_version: str = "test", features: pd.DataFrame | None = None,
               alias: str | None = None) -> FastAPI:
    """Fabrique l'application. Sans arguments : vrai registre et vraies données.
    Les tests passent un faux modèle et quelques lignes, pour ne dépendre de rien d'extérieur."""
    alias = alias or os.environ.get("EVREL_MODEL_ALIAS", "champion")

    bundle_dir = os.environ.get("EVREL_BUNDLE_DIR")      # défini dans le conteneur Docker

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Exécuté une seule fois au démarrage : on ne recharge pas le modèle à chaque requête.
        app.state.alias = alias
        if scorer is not None:                            # tests : faux modèle fourni
            app.state.scorer, app.state.model_version = scorer, model_version
            app.state.features = features
        elif bundle_dir:                                  # conteneur : paquet autonome, sans base MLflow
            from evrel.models.bundle import load_bundle
            app.state.scorer, info, app.state.features = load_bundle(bundle_dir)
            app.state.model_version, app.state.alias = info["model_version"], info["alias"]
        else:                                             # poste de travail : registre MLflow
            app.state.scorer, app.state.model_version = load_champion(alias)
            app.state.features = load_features()
        yield

    app = FastAPI(title="ChargeTriage",
                  description="Chaque soir, les bornes de recharge à inspecter en priorité le lendemain. "
                              "Page lisible : [/liste](/liste).",
                  version="1.2.0", lifespan=lifespan)
    app.include_router(router)
    return app


def score(request: Request, rows: pd.DataFrame) -> pd.Series:
    out = request.app.state.scorer.predict(as_model_input(rows))
    return pd.Series(out["score"].to_numpy(), index=rows.index)


def date_range(request: Request) -> tuple[date, date]:
    target = request.app.state.features["target_date"]
    return target.min().date(), target.max().date()


def build_ranking(request: Request, inspection_date: date, k: int) -> tuple[RankingResponse, float]:
    """Le cœur du service, partagé par /ranking (JSON) et /liste (page web)."""
    feats = request.app.state.features
    evening = feats[feats["target_date"] == pd.Timestamp(inspection_date)]
    if evening.empty:
        raise HTTPException(status_code=404, detail=f"Aucune variable calculée pour préparer le {inspection_date}.")
    evening = evening.assign(score=score(request, evening))
    ranked = evening.sort_values(["score", "post_id"], ascending=[False, True]).head(k)   # égalités : ordre fixe
    posts = [RankedPost(rank=i + 1, post_id=int(r.post_id), site=r.site, score=round(float(r.score), 6),
                        hw_faults_7d=float(r.hw_faults_7d))
             for i, r in enumerate(ranked.itertuples())]
    response = RankingResponse(inspection_date=inspection_date, features_date=evening["date"].iloc[0].date(),
                               model_version=request.app.state.model_version,
                               n_posts_scored=len(evening), posts=posts)
    return response, float(evening["score"].mean())


@router.get("/health", response_model=HealthResponse, tags=[MACHINES],
            summary="L'API fonctionne-t-elle, et avec quel modèle ?")
def health(request: Request) -> HealthResponse:
    first, last = date_range(request)
    return HealthResponse(status="ok", model_name=MODEL_NAME, alias=request.app.state.alias,
                          model_version=request.app.state.model_version,
                          first_inspection_date=first, last_inspection_date=last)


@router.post("/predict", response_model=PredictResponse, tags=[MACHINES],
             summary="Risque d'épisode de bornes dont on fournit les variables")
def predict(body: PredictRequest, request: Request) -> PredictResponse:
    rows = pd.DataFrame([p.model_dump() for p in body.posts])     # None devient NaN : le modèle sait faire
    return PredictResponse(model_version=request.app.state.model_version,
                           scores=score(request, rows).round(6).tolist())


@router.get("/ranking", response_model=RankingResponse, tags=[MACHINES],
            summary="Les k bornes à inspecter en priorité un jour donné",
            responses={404: {"description": "Aucune donnée pour préparer cette date"}})
def ranking(request: Request,
            inspection_date: date = Query(..., alias="date", description="Jour de l'inspection, AAAA-MM-JJ"),
            k: int = Query(10, ge=1, le=50, description="Nombre de bornes à inspecter")) -> RankingResponse:
    return build_ranking(request, inspection_date, k)[0]


@router.get("/liste", response_class=HTMLResponse, tags=[HUMAINS],
            summary="La liste du jour, en tableau lisible")
def liste(request: Request,
          inspection_date: date | None = Query(None, alias="date",
                                               description="Jour de l'inspection (par défaut : le dernier disponible)"),
          k: int = Query(10, ge=1, le=50)) -> HTMLResponse:
    first, last = date_range(request)
    inspection_date = inspection_date or last
    try:
        result, mean_score = build_ranking(request, inspection_date, k)
    except HTTPException as err:
        return HTMLResponse(error_page(err.detail, inspection_date, first, last, k), status_code=404)
    return HTMLResponse(ranking_page(result, mean_score, first, last, k))


@router.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    """Adresse nue : renvoie vers la page lisible."""
    return RedirectResponse("/liste")


app = create_app()