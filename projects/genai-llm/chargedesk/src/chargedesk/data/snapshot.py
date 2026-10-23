"""Vue de l'entrepot telle qu'elle etait connue un soir donne.

snapshot_connection(warehouse, evening) ouvre une base en memoire ou le
schema `marts` ne montre que ce qui etait connu au soir `evening` :
- les faits dont la date de disponibilite depasse ce soir sont retires ;
- les resultats du lendemain (episode_next_day, n_hits...) sont vides
  tant que leur date outcome_known_from n'est pas atteinte ;
- les dimensions (attributs fixes) sont reprises telles quelles ;
- fct_post_signals (table d'entrainement de ChargeTriage) n'est pas exposee :
  la presence d'une de ses lignes revele que le lendemain sera observable.

C'est la regle du soir courant. Elle sert au calcul des reponses attendues
du jeu d'evaluation, puis aux outils de l'agent : une requete ecrite sur
`marts` ne peut pas voir le futur, quelle qu'elle soit.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

# Une requete par table : {E} est remplace par le soir courant (DATE 'AAAA-MM-JJ').
SNAPSHOT_VIEWS: dict[str, str] = {
    # Dimensions : colonnes listees une par une. Une colonne ajoutee par erreur
    # (ex. une date de derniere recharge calculee sur toute la periode) ne passe pas.
    "dim_post": "select post_id, site, district, first_day from wh.marts.dim_post",
    "dim_site": "select site, district, n_posts from wh.marts.dim_site",
    "fct_post_day": "select * from wh.marts.fct_post_day where available_from <= {E}",
    "fct_evening_list": """
        select * replace (
            case when outcome_known_from <= {E} then episode_next_day end as episode_next_day
        )
        from wh.marts.fct_evening_list where evening <= {E}""",
    "fct_post_evening": "select * from wh.marts.fct_post_evening where available_from <= {E}",
    "fct_silent_alert": "select * from wh.marts.fct_silent_alert where available_from <= {E}",
    "fct_drift_month": "select * from wh.marts.fct_drift_month where available_from <= {E}",
    "fct_list_daily_hits": """
        select * replace (
            case when outcome_known_from <= {E} then n_hits end    as n_hits,
            case when outcome_known_from <= {E} then n_unknown end as n_unknown,
            case when outcome_known_from <= {E} then precision end as precision
        )
        from wh.marts.fct_list_daily_hits where evening <= {E}""",
}


def snapshot_connection(warehouse: Path | str, evening: date) -> duckdb.DuckDBPyConnection:
    """Connexion en memoire : `marts.*` = l'entrepot vu depuis le soir `evening`."""
    e = f"DATE '{evening.isoformat()}'"
    con = duckdb.connect()
    con.execute(f"ATTACH '{Path(warehouse).as_posix()}' AS wh (READ_ONLY)")
    con.execute("CREATE SCHEMA marts")
    for name, sql in SNAPSHOT_VIEWS.items():
        con.execute(f"CREATE VIEW marts.{name} AS {sql.format(E=e)}")
    return con


def full_connection(warehouse: Path | str) -> duckdb.DuckDBPyConnection:
    """Connexion en lecture seule sur tout l'entrepot (sert a detecter les fuites)."""
    return duckdb.connect(str(warehouse), read_only=True)
