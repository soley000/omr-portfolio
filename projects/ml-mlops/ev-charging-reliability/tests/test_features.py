import pandas as pd

from evrel.features import build_features
from evrel.split import assign_split


def make_inputs(faults_last_day=0):
    """Une borne, 10 jours, 5 sessions par jour, 1 défaut matériel les jours 4 et 5."""
    days = pd.date_range("2020-03-01", periods=10, freq="D")
    faults = [0, 0, 0, 1, 1, 0, 0, 0, 0, faults_last_day]
    daily = pd.DataFrame({
        "post_id": 1, "site": "Park A", "date": days,
        "n_sessions": 5, "n_hw_faults": faults, "energy_kwh": 50.0,
        "hw_fault_rate": [f / 5 for f in faults], "baseline_rate": 0.0,
        "is_episode": [0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    })
    sessions = pd.DataFrame({
        "post_id": 1, "district": "Nanhu", "start_time": days + pd.Timedelta(hours=10),
        "is_empty": 0, "is_short": 0, "cause_family": "Fin normale",
    })
    weather = pd.DataFrame({"district": "Nanhu", "date": days, "temperature_c": 10.0,
                            "precipitation_mm": 0.0, "humidity_pct": 50})
    return daily, sessions, weather


def test_target_is_next_day_episode():
    feats = build_features(*make_inputs(), holidays=[])
    row = feats[feats["date"] == "2020-03-04"].iloc[0]
    assert row["target_date"] == pd.Timestamp("2020-03-05")
    assert row["y"] == 1                                   # épisode le 5 mars
    assert len(feats) == 9                                 # le dernier jour n'a pas de lendemain connu


def test_rolling_windows_include_today_only_past():
    feats = build_features(*make_inputs(), holidays=[])
    row = feats[feats["date"] == "2020-03-05"].iloc[0]
    assert row["hw_faults_d0"] == 1
    assert row["hw_faults_3d"] == 2                        # 3, 4 et 5 mars
    assert row["days_since_episode"] == 0


def test_no_leakage_from_the_future():
    """Changer ce qui se passe le dernier jour ne doit changer aucune variable des jours précédents."""
    a = build_features(*make_inputs(faults_last_day=0), holidays=[])
    b = build_features(*make_inputs(faults_last_day=4), holidays=[])
    cols = [c for c in a.columns if c != "y"]
    before_last = a["date"] < "2020-03-10"
    pd.testing.assert_frame_equal(a.loc[before_last, cols], b.loc[before_last, cols])


def test_split_uses_target_date():
    dates = pd.Series(pd.to_datetime(["2020-12-31", "2021-01-01", "2021-05-01", "2021-09-01"]))
    periods = {"train": ["2020-01-01", "2020-12-31"], "valid": ["2021-01-01", "2021-04-30"],
               "test": ["2021-05-01", "2021-08-31"], "replay": ["2021-09-01", "2021-12-31"]}
    assert assign_split(dates, periods).tolist() == ["train", "valid", "test", "replay"]

def test_model_features_exclude_dropped_ones():
    from evrel.features import DROPPED_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES

    assert not set(DROPPED_FEATURES) & set(MODEL_FEATURES)
    assert set(DROPPED_FEATURES) <= set(NUMERIC_FEATURES)     # pas de faute de frappe dans les noms
    assert len(MODEL_FEATURES) == 19