"""Tests automatiques de la chaîne complète sur de FAUSSES données.

JSON bruts -> Parquet -> dbt run -> dbt test -> lecture par le tableau de bord.
On vérifie aussi que les anomalies plantées volontairement sont bien DÉTECTÉES.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import make_fake_raw as fake                       # noqa: E402
from app import data as app_data                   # noqa: E402
from pipeline import check_output                  # noqa: E402


def _dbt_executable() -> str:
    beside_python = Path(sys.executable).parent / "dbt"
    return str(beside_python) if beside_python.exists() else (shutil.which("dbt") or "dbt")


def _run(cmd: list[str], env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mobilityflow")
    data_dir, warehouse_dir = tmp / "data", tmp / "warehouse"
    warehouse_dir.mkdir()
    fake.build(data_dir)

    env = {
        **os.environ,
        "MOBILITYFLOW_DATA_DIR": str(data_dir),
        "MOBILITYFLOW_WAREHOUSE_PATH": str(warehouse_dir / "mobilityflow.duckdb"),
        "DBT_TARGET_PATH": str(tmp / "dbt_target"),
        "DBT_LOG_PATH": str(tmp / "dbt_logs"),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "False",
    }
    for day in fake.DAYS:
        done = _run([sys.executable, str(ROOT / "pipeline" / "json_to_parquet.py"),
                     "--data", str(data_dir), "--date", day], env, ROOT)
        assert done.returncode == 0, done.stdout + done.stderr

    dbt = _dbt_executable()
    run = _run([dbt, "run", "--profiles-dir", "."], env, ROOT / "dbt")
    test = _run([dbt, "test", "--profiles-dir", "."], env, ROOT / "dbt")
    return {"data_dir": data_dir, "warehouse": warehouse_dir / "mobilityflow.duckdb",
            "run": run, "test": test}


# ---------------------------------------------------------------- conversion Parquet

def test_parquet_has_expected_rows(built):
    import pandas as pd
    for day in fake.DAYS:
        path = built["data_dir"] / "parquet" / "station_status" / f"date_paris={day}" / "station_status.parquet"
        df = pd.read_parquet(path)
        minutes = fake.minutes_per_day() - (fake.gap_minutes() if day == fake.GAP_DAY else 0)
        assert len(df) == minutes * fake.N_STATIONS
        assert df["station_id"].nunique() == fake.N_STATIONS


def test_check_output_accepts_good_day_and_rejects_missing_day(built):
    assert check_output.check(built["data_dir"], fake.DAYS[0]) is None
    assert check_output.check(built["data_dir"], "2030-01-01") is not None


# ---------------------------------------------------------------- dbt

def test_dbt_run_succeeds(built):
    assert built["run"].returncode == 0, built["run"].stdout + built["run"].stderr


def test_dbt_tests_have_no_error(built):
    out = built["test"].stdout + built["test"].stderr
    assert built["test"].returncode == 0, out


def test_dbt_warns_about_planted_anomalies(built):
    out = built["test"].stdout
    assert "WARN" in out, "les anomalies plantées devraient produire des avertissements dbt"
    assert "assert_station_capacity_matches_observed" in out
    assert "assert_station_coordinates_valid" in out


# ---------------------------------------------------------------- lecture par le tableau de bord

@pytest.fixture(scope="session")
def tables(built):
    return app_data.load_warehouse(str(built["warehouse"]))


def test_dashboard_loads_all_tables(tables):
    for name in ("stations", "hours", "collection", "unchanged", "meta"):
        assert name in tables and len(tables[name]) > 0, name
    assert len(tables["stations"]) == fake.N_STATIONS


def test_capacity_gap_is_detected_on_one_station(tables):
    gap = tables["stations"].loc[tables["stations"]["has_capacity_gap"]]
    assert list(gap["station_id"]) == ["4"]


def test_station_without_coordinates_is_visible(tables):
    st = tables["stations"].set_index("station_id")
    assert st.loc["11", "lat"] == 0 and st.loc["11", "lon"] == 0


def test_collection_gap_is_visible(tables):
    c = tables["collection"]
    missing = c.loc[c["date_paris"].astype(str) == fake.GAP_DAY, "missing_snapshots"].sum()
    assert missing >= fake.gap_minutes() - 1


def test_often_empty_and_often_full_stations(tables):
    rates = app_data.weighted_rates(tables["hours"], ["station_id"])
    r = rates.set_index("station_id")
    assert r.loc["1", "pct_empty"] > 0.2
    assert r.loc["2", "pct_full"] > 0.2
    assert r["pct_empty"].dropna().between(0, 1).all()
    assert r["pct_full"].dropna().between(0, 1).all()


def test_not_installed_station_is_not_counted_in_service(tables):
    h = tables["hours"]
    assert h.loc[h["station_id"] == "9", "snapshots_in_service"].fillna(0).sum() == 0


def test_frozen_station_has_the_longest_unchanged_period(tables):
    u = tables["unchanged"].set_index("station_id")["longest_unchanged_minutes"]
    assert u.idxmax() == "5"


# ---------------------------------------------------------------- petites fonctions d'affichage

def test_formatting_helpers():
    assert app_data.fmt_minutes(95) == "1 h 35"
    assert app_data.fmt_minutes(40) == "40 min"
    assert app_data.fmt_pct(0.426, 0) == "43 %"
    assert app_data.fmt_pct(None) == "n/d"