import pandas as pd

from evrel.data.clean import LEAKY_COLS, clean_sessions
from evrel.data.load import FLAG_COLS


def make_raw():
    """Quatre sessions fabriquées, dans le désordre, avec les colonnes du fichier brut."""
    start = pd.to_datetime(["2020-03-02 10:00", "2019-12-31 22:00", "2020-03-01 09:00", "2020-03-01 12:00"])
    df = pd.DataFrame({
        "user_id": [1, 2, 3, 4],
        "post_id": [1, 1, 1, 2],
        "site": "Park A",
        "district": "Nanhu",
        "order_created_at": start,
        "energy_kwh": [10.0, 5.0, 0.0, 8.0],
        "electricity_cost": 1.0, "service_charge": 1.0, "amount": 2.0, "amount_paid": 2.0,
        "start_time": start,
        "end_time": start + pd.to_timedelta([30, 20, 0.5, 40], unit="min"),
        "paid_at": start + pd.Timedelta(hours=1),
        "temperature_c": 10.0, "humidity_pct": 50, "precipitation_mm": 0.0,
        "end_cause": ["Charging ends normally", "Charging ends normally",
                      "DC Output Fault", "Faulty charging connection"],
    })
    for col in FLAG_COLS:
        df[col] = 0
    return df


def test_period_starts_in_2020():
    clean = clean_sessions(make_raw(), start_date="2020-01-01")
    assert clean["start_time"].min() >= pd.Timestamp("2020-01-01")
    assert len(clean) == 3


def test_empty_sessions_are_kept_and_flagged():
    clean = clean_sessions(make_raw(), start_date="2020-01-01")
    empty = clean[clean["energy_kwh"] == 0]
    assert len(empty) == 1
    assert empty["is_empty"].iloc[0] == 1
    assert empty["is_short"].iloc[0] == 1


def test_leaky_and_author_columns_are_removed():
    clean = clean_sessions(make_raw(), start_date="2020-01-01")
    for col in LEAKY_COLS + FLAG_COLS:
        assert col not in clean.columns


def test_families_and_order():
    clean = clean_sessions(make_raw(), start_date="2020-01-01")
    assert clean["post_id"].tolist() == [1, 1, 2]
    assert clean.loc[0, "start_time"] < clean.loc[1, "start_time"]   # trié dans le temps par borne
    assert clean.loc[0, "cause_family"] == "Défaut matériel"
    assert clean.loc[2, "cause_family"] == "Ambiguë (exclue)"