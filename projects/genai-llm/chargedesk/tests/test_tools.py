"""Outils de l'agent : periodes, resultats sur l'entrepot fictif, erreurs propres."""
import json
from datetime import date

import pytest

from chargedesk.data.snapshot import snapshot_connection
from chargedesk.tools.periods import PeriodError, resolve_period
from chargedesk.tools.registry import call_tool, tool_specs

E = date(2021, 10, 5)


@pytest.mark.parametrize("name,expected", [
    ("last_7_days", (date(2021, 9, 29), date(2021, 10, 5))),
    ("previous_7_days", (date(2021, 9, 22), date(2021, 9, 28))),
    ("month_to_date", (date(2021, 10, 1), date(2021, 10, 5))),
    ("previous_month", (date(2021, 9, 1), date(2021, 9, 30))),
    ("year_to_date", (date(2021, 1, 1), date(2021, 10, 5))),
])
def test_named_periods(name, expected):
    assert resolve_period(E, name) == expected


def test_years_back_and_leap_day():
    assert resolve_period(E, "month_to_date", years_back=1) == (date(2020, 10, 1), date(2020, 10, 5))
    a, b = resolve_period(date(2021, 2, 28), "custom", date(2021, 2, 28), date(2021, 2, 28), years_back=0)
    assert a == b == date(2021, 2, 28)


def test_future_and_too_old_periods_are_rejected():
    with pytest.raises(PeriodError):
        resolve_period(E, "custom", date(2021, 10, 1), date(2021, 10, 6))
    with pytest.raises(PeriodError):
        resolve_period(E, "custom", date(2019, 12, 1), date(2019, 12, 31))


def test_specs_are_plain_json_schema():
    specs = tool_specs()
    text = json.dumps(specs)
    assert len(specs) == 12
    assert "anyOf" not in text and "$ref" not in text and '"title"' not in text


@pytest.fixture
def con(fake_warehouse):
    c = snapshot_connection(fake_warehouse, E)
    yield c
    c.close()


def test_metric_and_comparison_agree(con):
    ok, a = call_tool(con, E, "get_metric", {"metric": "hw_faults", "period": "month_to_date"})
    ok2, c = call_tool(con, E, "compare_periods", {"metric": "hw_faults", "period_a": "month_to_date",
                                                   "period_b": "month_to_date", "years_back_b": 1})
    assert ok and ok2
    assert c["difference_a_minus_b"] == c["period_a"]["value"] - c["period_b"]["value"]
    assert c["period_a"]["value"] == a["value"]


def test_evening_list_and_signals(con):
    ok, lst = call_tool(con, E, "get_evening_list", {})
    assert ok and lst["list"][0]["post_id"] == 23 and lst["n_listed"] == 10
    ok, sig = call_tool(con, E, "get_post_signals", {"post_id": 23})
    assert ok and sig["in_champion_list"]


def test_silent_status_is_current_state(con):
    ok, st = call_tool(con, E, "get_post_status", {"site": "Technology Park"})
    assert ok
    assert st["n_silent"] == st["n_posts"] == 4   # muettes depuis le 29/09 dans l'entrepot fictif


def test_list_hits_refuses_tonight(con):
    ok, res = call_tool(con, E, "get_list_hits", {"evening": "2021-10-05"})
    assert not ok and "error" in res


def test_bad_arguments_return_an_error_not_a_crash(con):
    for name, args in [("get_metric", {"metric": "profit", "period": "last_7_days"}),
                       ("get_metric", "{pas du json"),
                       ("outil_inconnu", {}),
                       ("get_metric", {"metric": "sessions", "period": "last_7_days", "site": "Lune"}),
                       ("run_sql", {"query": "DROP TABLE marts.fct_post_day"}),
                       ("run_sql", {"query": "select * from marts.fct_post_signals"})]:
        ok, res = call_tool(con, E, name, args)
        assert not ok and res["error"], (name, args)


def test_tools_never_see_the_future(con):
    ok, res = call_tool(con, E, "run_sql", {"query": "select max(day) as d from marts.fct_post_day"})
    assert ok and str(res["rows"][0]["d"]) <= "2021-10-05"


def test_sql_error_goes_back_to_the_llm(con):
    ok, res = call_tool(con, E, "run_sql", {"query": "select site_id from marts.dim_post"})
    assert not ok and res["error"].startswith("erreur SQL")
    assert "marts.fct_post_day(" in res["error"] and "n_hw_faults" in res["error"]
    assert "fct_post_signals" not in res["error"]          # la table interdite reste invisible


def test_list_hits_says_which_posts(con):
    ok, res = call_tool(con, E, "get_list_hits", {"evening": "2021-10-04"})
    assert ok and len(res["champion_posts"]) == 10
    assert sum(p["episode_next_day"] for p in res["champion_posts"]) == res["champion"]["n_hits"]


def test_rank_posts_by_faults_and_rate(con):
    ok, res = call_tool(con, E, "rank_posts", {"metric": "hw_faults", "period": "last_7_days", "top": 5})
    assert ok and len(res["posts"]) == 5
    vals = [p["value"] for p in res["posts"]]
    assert vals == sorted(vals, reverse=True) and res["posts"][0]["rank"] == 1
    ok, res = call_tool(con, E, "rank_posts", {"metric": "hw_fault_rate", "period": "last_7_days",
                                               "site": "Shopping Mall", "min_sessions": 1})
    assert ok and all(p["site"] == "Shopping Mall" for p in res["posts"]) and "note" in res
    # bornes muettes (0 recharge) ignorees pour un taux
    ok, res = call_tool(con, E, "rank_posts", {"metric": "hw_fault_rate", "period": "last_7_days",
                                               "site": "Technology Park"})
    assert ok and res["posts"] == []


def test_rank_posts_never_sees_the_future(con):
    ok, res = call_tool(con, E, "rank_posts", {"metric": "sessions", "period": "custom",
                                               "start": "2021-10-01", "end": "2021-10-09"})
    assert not ok
