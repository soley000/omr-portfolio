"""Questions proposees sur la page, ecrites en entier (un clic les pose).

Trois familles : sur une borne de la liste, sur un site hors liste, et des questions frequentes.
Aucune ne reprend mot pour mot une question du jeu de test (un test le verifie).
"""
from __future__ import annotations

POST_QUESTIONS = [
    {"id": "why", "label": "Pourquoi ?", "text": "Pourquoi la borne {post_id} est-elle dans la liste ce soir ?"},
    {"id": "faults", "label": "Ses pannes",
     "text": "Combien de pannes matérielles la borne {post_id} a-t-elle eues sur les 7 derniers jours, comparé aux 7 jours d'avant ?"},
]

SITE_QUESTIONS = [
    {"id": "status", "label": "Vérifier ce site",
     "text": "Les bornes du site {site} sont-elles à l'arrêt, et depuis quand n'ont-elles plus de recharge ?"},
]

FREQUENT = [
    {"id": "trust", "label": "Peut-on se fier à la liste en ce moment ?",
     "text": "Sur les dernières semaines, quelle part des bornes listées a vraiment eu un épisode le lendemain ?"},
    {"id": "model_vs_rule", "label": "Qu'est-ce que le modèle repère, que le simple comptage des pannes ne voit pas ?",
     "text": "Quelles bornes le modèle met-il dans sa liste ce soir alors que la règle simple ne les retient pas ?"},
    {"id": "network_week", "label": "Combien de pannes sur le réseau cette semaine ?",
     "text": "Combien de pannes matérielles sur tout le réseau ces 7 derniers jours, comparé aux 7 jours d'avant ?"},
    {"id": "yesterday", "label": "Les bornes listées hier ont-elles vraiment eu des pannes ?",
     "text": "Parmi les bornes de la liste d'hier soir, lesquelles ont vraiment eu un épisode de pannes le lendemain ?"},
]


def all_rendered(sites: list[str], posts: list[int]) -> list[str]:
    """Toutes les questions que la page peut proposer (pour le test anti-reprise du jeu de test)."""
    out = [q["text"] for q in FREQUENT]
    out += [q["text"].format(post_id=p) for q in POST_QUESTIONS for p in posts]
    out += [q["text"].format(site=s) for q in SITE_QUESTIONS for s in sites]
    return out
