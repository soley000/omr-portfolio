import duckdb
import pandas as pd
import pytest

from chargedesk.data.load_raw import load_raw


def _make_sources(tmp_path):
    src = tmp_path / "src"
    (src / "processed").mkdir(parents=True)
    (src / "monitoring").mkdir()
    pd.DataFrame({"post_id": [1, 2, 3], "n_hw_faults": [0, 1, 2]}).to_parquet(src / "processed" / "daily.parquet")
    pd.DataFrame({"post_id": [5], "site": ["Park B"]}).to_csv(src / "monitoring" / "silent.csv", index=False)
    return src, {"daily": "processed/daily.parquet", "silent": "monitoring/silent.csv"}


def test_load_creates_tables_and_log(tmp_path):
    src, sources = _make_sources(tmp_path)
    wh = tmp_path / "wh" / "test.duckdb"
    log = load_raw(src, wh, sources, {"daily": 3, "silent": 1})
    assert list(log["rows"]) == [3, 1]
    con = duckdb.connect(str(wh), read_only=True)
    assert con.execute("SELECT count(*) FROM raw.daily").fetchone()[0] == 3
    assert con.execute("SELECT count(*) FROM raw.load_log").fetchone()[0] == 2
    con.close()


def test_wrong_row_count_stops_before_writing(tmp_path):
    src, sources = _make_sources(tmp_path)
    wh = tmp_path / "test.duckdb"
    with pytest.raises(ValueError, match="attendues"):
        load_raw(src, wh, sources, {"daily": 99})
    assert not wh.exists()


def test_missing_source_is_reported(tmp_path):
    src, sources = _make_sources(tmp_path)
    sources["absent"] = "processed/absent.parquet"
    with pytest.raises(FileNotFoundError):
        load_raw(src, tmp_path / "test.duckdb", sources)


def test_sources_are_never_modified(tmp_path):
    src, sources = _make_sources(tmp_path)
    files = [p for p in src.rglob("*") if p.is_file()]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in files}
    load_raw(src, tmp_path / "test.duckdb", sources)
    after = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in files}
    assert before == after