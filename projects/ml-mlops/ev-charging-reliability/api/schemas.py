"""Formats des requêtes et des réponses de l'API (Pydantic) : ce qui entre et ce qui sort, contrôlé."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

EXAMPLE_POST = {
    "site": "Wholesale Market",
    "hw_faults_d0": 2, "hw_faults_3d": 3, "hw_faults_7d": 4, "hw_faults_28d": 6,
    "hw_rate_7d": 0.25, "hw_rate_28d": 0.12, "hw_rate_trend": 0.13, "hist_hw_rate": 0.09,
    "episode_d0": 1, "episodes_28d": 2, "days_since_episode": 0,
    "empty_share_7d": 0.12, "short_share_7d": 0.06,
    "sessions_d0": 5, "sessions_7d": 16, "sessions_28d": 50, "usage_trend": 0.1, "idle_days_7d": 0,
    "temperature_c": 28.5,
}


class PostFeatures(BaseModel):
    """Les variables d'une borne, calculées le soir J avec les seules données connues ce soir-là."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": EXAMPLE_POST})

    site: str = Field(min_length=1, description="Nom du site (un site inconnu est accepté, sans effet)")
    # Défauts récents
    hw_faults_d0: float = Field(ge=0, description="Pannes matérielles le jour J")
    hw_faults_3d: float = Field(ge=0, description="Pannes matérielles sur 3 jours")
    hw_faults_7d: float = Field(ge=0, description="Pannes matérielles sur 7 jours")
    hw_faults_28d: float = Field(ge=0, description="Pannes matérielles sur 28 jours")
    hw_rate_7d: float | None = Field(None, ge=0, le=1, description="Taux de pannes sur 7 jours (vide si aucune recharge)")
    hw_rate_28d: float | None = Field(None, ge=0, le=1, description="Taux de pannes sur 28 jours")
    hw_rate_trend: float | None = Field(None, ge=-1, le=1, description="Taux 7 jours moins taux 28 jours")
    hist_hw_rate: float | None = Field(None, ge=0, le=1, description="Taux de pannes depuis la mise en service")
    # Épisodes passés
    episode_d0: float = Field(ge=0, le=1, description="Épisode le jour J (0 ou 1)")
    episodes_28d: float = Field(ge=0, description="Épisodes sur 28 jours")
    days_since_episode: float = Field(ge=0, le=365, description="Jours depuis le dernier épisode (365 si aucun)")
    # Signaux faibles
    empty_share_7d: float | None = Field(None, ge=0, le=1, description="Part de recharges à 0 kWh sur 7 jours")
    short_share_7d: float | None = Field(None, ge=0, le=1, description="Part de recharges très courtes sur 7 jours")
    # Usage
    sessions_d0: float = Field(ge=0, description="Recharges le jour J")
    sessions_7d: float = Field(ge=0, description="Recharges sur 7 jours")
    sessions_28d: float = Field(ge=0, description="Recharges sur 28 jours")
    usage_trend: float | None = Field(None, description="Évolution de l'usage, 7 jours contre 28 jours")
    idle_days_7d: float = Field(ge=0, le=7, description="Jours sans recharge sur 7 jours")
    # Météo
    temperature_c: float | None = Field(None, ge=-40, le=60, description="Température du jour J (°C)")


class PredictRequest(BaseModel):
    posts: list[PostFeatures] = Field(min_length=1, max_length=500)


class PredictResponse(BaseModel):
    model_version: str
    scores: list[float] = Field(description="Un score par borne, dans l'ordre de la requête")


class RankedPost(BaseModel):
    rank: int
    post_id: int
    site: str
    score: float
    hw_faults_7d: float = Field(description="Repère pour le technicien : pannes sur 7 jours")


class RankingResponse(BaseModel):
    inspection_date: date = Field(description="Jour de l'inspection (J+1)")
    features_date: date = Field(description="Soir où les variables ont été calculées (J)")
    model_version: str
    n_posts_scored: int
    posts: list[RankedPost]


class HealthResponse(BaseModel):
    status: str
    model_name: str
    alias: str
    model_version: str
    first_inspection_date: date
    last_inspection_date: date