"""Tests du contrôle de santé et de l'alerte Airflow (sans Airflow)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dags"))

import mobilityflow_alerts as alerts            # noqa: E402
from monitoring import health_check as hc       # noqa: E402

NOW = datetime(2026, 10, 10, 20, 0, tzinfo=timezone.utc)


def test_collector_alive_and_stopped():
    assert hc.collector_check(NOW, NOW - timedelta(minutes=1)).level == hc.OK
    assert hc.collector_check(NOW, NOW - timedelta(minutes=20)).level == hc.ALERT
    assert hc.collector_check(NOW, None).level == hc.ALERT


def test_completeness_levels():
    assert hc.completeness_check(60).level == hc.OK
    assert hc.completeness_check(40).level == hc.WARN


def test_warehouse_freshness():
    assert hc.warehouse_check(NOW, NOW - timedelta(hours=17)).level == hc.OK
    assert hc.warehouse_check(NOW, NOW - timedelta(hours=40)).level == hc.ALERT
    assert hc.warehouse_check(NOW, None).level == hc.ALERT


def test_failures_only_count_when_recent():
    old = {"time": (NOW - timedelta(hours=30)).isoformat(), "task": "dbt_test"}
    new = {"time": (NOW - timedelta(hours=2)).isoformat(), "task": "dbt_run"}
    assert hc.failures_check(NOW, []).level == hc.OK
    assert hc.failures_check(NOW, [old]).level == hc.OK
    assert hc.failures_check(NOW, [old, new]).level == hc.ALERT


def test_log_failure_writes_one_json_line_then_health_check_sees_it(tmp_path, monkeypatch):
    monkeypatch.setenv("MOBILITYFLOW_DATA_DIR", str(tmp_path))

    class FakeTask:
        dag_id, task_id = "mobilityflow_daily", "dbt_run"

    alerts.log_failure({"task_instance": FakeTask(), "run_id": "manual__test"})
    lines = (tmp_path / "monitoring" / "failures.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["task"] == "dbt_run"

    now = datetime.now(timezone.utc)
    assert hc.failures_check(now, hc.read_failures(tmp_path)).level == hc.ALERT


def test_log_failure_never_raises(monkeypatch):
    monkeypatch.setenv("MOBILITYFLOW_DATA_DIR", os.devnull + "/impossible")
    alerts.log_failure({})          # ne doit pas lever d'erreur


def test_run_checks_on_an_empty_folder_gives_alerts_not_crashes(tmp_path):
    levels = {c.name: c.level for c in hc.run_checks(tmp_path, NOW)}
    assert levels["Collecteur vivant"] == hc.ALERT
    assert levels["Entrepot a jour"] == hc.ALERT