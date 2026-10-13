import pytest

from evrel.data.load import FLAG_COLS, load_sessions


@pytest.fixture(scope="module")
def sessions():
    return load_sessions()


def test_volume(sessions):
    assert len(sessions) == 441_077
    assert sessions["post_id"].nunique() == 92


def test_sites_are_clean(sessions):
    assert sessions["site"].nunique() == 13
    assert not sessions["site"].str.contains("\t").any()


def test_dates_are_parsed(sessions):
    assert sessions["start_time"].notna().all()


def test_exactly_one_end_cause(sessions):
    causes = [c for c in FLAG_COLS if c != "is_abnormal"]
    assert (sessions[causes].sum(axis=1) == 1).all()

def test_weather_has_one_row_per_district_and_day():
    from evrel.data.load import load_weather
    w = load_weather()
    assert not w.duplicated(["district", "date"]).any()   # sinon les bornes sont dupliquées ces jours-là