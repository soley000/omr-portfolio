"""Page web lisible par un humain : la liste du soir sous forme de tableau, en français."""
from __future__ import annotations

from datetime import date
from html import escape

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

STYLE = """
body { font-family: system-ui, sans-serif; margin: 0; background: #f7f7f5; color: #1f1f1f; }
main { max-width: 820px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; }
.sub { color: #5c5c5c; margin: 0 0 20px; }
form { margin-bottom: 20px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
input, button { font: inherit; padding: 6px 10px; border: 1px solid #b9b8b3; border-radius: 6px; }
button { background: #2a78d6; color: white; border-color: #2a78d6; cursor: pointer; }
table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ecebe7; }
th { background: #ecebe7; font-weight: 600; font-size: 0.9rem; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
td.id { white-space: nowrap; }
.bar { height: 8px; background: #2a78d6; border-radius: 4px; }
.note { color: #5c5c5c; font-size: 0.9rem; margin-top: 16px; }
.error { background: #fdecea; border: 1px solid #e34948; padding: 12px; border-radius: 8px; }
"""


def french_date(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"


def _layout(title: str, body: str, selected: date, first: date, last: date, k: int) -> str:
    form = (f'<form action="/liste" method="get">'
            f'<label>Jour de l\'inspection <input type="date" name="date" value="{selected}" '
            f'min="{first}" max="{last}"></label>'
            f'<label>Nombre de bornes <input type="number" name="k" value="{k}" min="1" max="50"></label>'
            f'<button type="submit">Afficher</button></form>')
    return (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>ChargeTriage</title><style>{STYLE}</style></head>'
            f'<body><main><h1>{escape(title)}</h1>{form}{body}</main></body></html>')


def ranking_page(ranking, mean_score: float, first: date, last: date, k: int) -> str:
    """ranking : une RankingResponse (la même réponse que /ranking, mise en forme)."""
    top = max((p.score for p in ranking.posts), default=1) or 1
    # Le champion renvoie une probabilité ; la règle de repli, un nombre de pannes (après un rollback).
    is_proba = all(0 <= p.score <= 1 for p in ranking.posts)
    fmt = (lambda x: f"{x:.1%}".replace(".", ",").replace("%", " %")) if is_proba else (lambda x: f"{x:.0f}")
    note = ("Risque d'épisode : probabilité que la borne connaisse un épisode anormal de pannes matérielles "
            "ce jour-là." if is_proba else
            "Le modèle est remplacé par la règle de repli : score = pannes matérielles sur 7 jours.")
    rows = "".join(
        f"<tr><td class='num'>{p.rank}</td><td class='id'>Borne {p.post_id}</td><td>{escape(p.site)}</td>"
        f"<td class='num'>{fmt(p.score)}</td>"
        f"<td style='width:25%'><div class='bar' style='width:{p.score / top:.0%}'></div></td>"
        f"<td class='num'>{p.hw_faults_7d:.0f}</td></tr>"
        for p in ranking.posts)
    body = (f"<p class='sub'>Liste calculée le {french_date(ranking.features_date)} au soir, "
            f"avec le modèle version {escape(ranking.model_version)}, parmi {ranking.n_posts_scored} bornes.</p>"
            "<table><thead><tr><th>Priorité</th><th>Borne</th><th>Site</th>"
            f"<th>{'Risque d’épisode' if is_proba else 'Score (règle de repli)'}</th><th></th>"
            "<th>Pannes sur 7 jours</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            f"<p class='note'>{note} Moyenne des {ranking.n_posts_scored} bornes ce soir-là : "
            f"{fmt(mean_score)}.</p>")
    return _layout(f"Bornes à inspecter le {french_date(ranking.inspection_date)}", body,
                   ranking.inspection_date, first, last, k)


def error_page(message: str, selected: date, first: date, last: date, k: int) -> str:
    body = (f"<p class='error'>{escape(message)}</p>"
            f"<p class='note'>Données disponibles du {french_date(first)} au {french_date(last)}.</p>")
    return _layout("Bornes à inspecter", body, selected, first, last, k)