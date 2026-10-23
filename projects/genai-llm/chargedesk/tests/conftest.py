"""Entrepot fictif, de meme structure que les marts de ChargeDesk.

Sert aux tests de la regle du soir courant et du jeu d'evaluation, sans
jamais toucher aux vraies donnees (la CI n'y a pas acces).
"""
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

SITES = {
    "Tourist Attraction": range(1, 9), "Technology Park": range(17, 21),
    "Shopping Mall": range(21, 29), "Park A": range(33, 41), "Park B": range(49, 54),
    "Bus Station": range(54, 62), "Expressway Service District B": range(70, 74),
    "Expressway Service District C": range(79, 87), "Government Agency": range(41, 49),
    "Wholesale Market": range(87, 93),
}
# Bornes muettes : (premier jour sans recharge, jour de reprise ou None)
SILENT = {
    **{p: (date(2021, 9, 29), None) for p in range(17, 21)},
    **{p: (date(2021, 12, 14), date(2021, 12, 27)) for p in range(1, 9)},
    26: (date(2021, 9, 23), None),
    70: (date(2021, 11, 17), None),
}
START, END = date(2020, 1, 1), date(2021, 12, 31)
REPLAY = (date(2021, 8, 31), date(2021, 12, 30))


def _days(a, b):
    return [a + timedelta(d) for d in range((b - a).days + 1)]


def make_warehouse(path):
    rng = np.random.default_rng(0)
    posts = [(p, s) for s, ps in SITES.items() for p in ps]
    rows = []
    for p, s in posts:
        for d in _days(START, END):
            off = SILENT.get(p)
            silent = off and d >= off[0] and (off[1] is None or d < off[1])
            n = 0 if silent else int(rng.integers(1, 12))
            f = 0 if n == 0 else int(rng.integers(0, max(1, n // 2)))
            rows.append((p, s, "District", d, n, f, float(n * 20.5), f / n if n else None, 0.1, f >= 2, True, d))
    day = pd.DataFrame(rows, columns=["post_id", "site", "district", "day", "n_sessions", "n_hw_faults",
                                      "energy_kwh", "hw_fault_rate", "baseline_rate", "is_episode",
                                      "is_observable", "available_from"])
    evenings = _days(*REPLAY)
    lst, hits, sig = [], [], []
    for e in evenings:
        t = e + timedelta(1)
        for model in ("champion", "fallback"):
            chosen = rng.choice([p for p, _ in posts], 10, replace=False)
            if e == date(2021, 10, 5) and model == "champion" and 23 not in chosen:
                chosen[0] = 23   # comme dans les vraies donnees : borne 23 en tete le 05/10
            scores = sorted(rng.uniform(0.1, 0.5, 10), reverse=True)
            outs = rng.random(10) < 0.2
            for r, (p, sc, y) in enumerate(zip(chosen, scores, outs), 1):
                lst.append((e, t, model, r, int(p), dict(posts)[int(p)], float(sc), bool(y), t, 0.08, len(posts)))
            hits.append((e, t, model, 10, int(outs.sum()), 0, float(outs.mean()), t))
        for p, s in posts:
            sig.append((int(p), s, e, t, float(rng.integers(0, 15)), bool(rng.random() < 0.1), t))
    lst = pd.DataFrame(lst, columns=["evening", "target_date", "model", "rank", "post_id", "site", "score",
                                     "episode_next_day", "outcome_known_from", "mean_score_all", "n_posts"])
    hits = pd.DataFrame(hits, columns=["evening", "target_date", "model", "n_listed", "n_hits", "n_unknown",
                                       "precision", "outcome_known_from"])
    sig = pd.DataFrame(sig, columns=["post_id", "site", "evening", "target_date", "hw_faults_7d",
                                     "episode_next_day", "outcome_known_from"])
    alerts = pd.DataFrame([(p, s, d + timedelta(6), d - timedelta(1), 7, d + timedelta(6))
                           for p, s in posts if p in SILENT for d in [SILENT[p][0]]],
                          columns=["post_id", "site", "alert_date", "last_session_date", "days_silent", "available_from"])
    drift = pd.DataFrame([("hw_faults_7d", "2021-09", date(2021, 9, 1), 0.2, "watch", date(2021, 9, 30))],
                         columns=["feature", "month", "month_start", "psi", "level", "available_from"])
    dim_post = pd.DataFrame([(p, s, "District", START) for p, s in posts],
                            columns=["post_id", "site", "district", "first_day"])
    dim_site = dim_post.groupby("site").agg(district=("district", "first"), n_posts=("post_id", "count")).reset_index()

    con = duckdb.connect(str(path))
    con.execute("create schema marts; create schema raw")
    for name, df in {"fct_post_day": day, "fct_evening_list": lst, "fct_list_daily_hits": hits,
                     "fct_post_signals": sig, "fct_silent_alert": alerts, "fct_drift_month": drift,
                     "dim_post": dim_post, "dim_site": dim_site}.items():
        con.register("_df", df)
        con.execute(f"create table marts.{name} as select * from _df")
        con.unregister("_df")
    # fct_post_evening : meme SQL que le modele dbt, applique a l'entrepot fictif
    sql = (Path(__file__).parents[1] / "dbt/models/marts/fct_post_evening.sql").read_text(encoding="utf-8")
    sql = sql.replace("{{ ref('fct_post_day') }}", "marts.fct_post_day")
    con.execute(f"create table marts.fct_post_evening as {sql}")
    con.execute("create table raw.load_log as select 'fake' as source, 'abc' as sha256")
    con.close()
    return path


@pytest.fixture(scope="session")
def fake_warehouse(tmp_path_factory):
    return make_warehouse(tmp_path_factory.mktemp("wh") / "fake.duckdb")
