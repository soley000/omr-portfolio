import pandas as pd

from evrel.target import add_hardware_fault, add_past_baseline, daily_post_table


def make_sessions(rows):
    """Petit jeu de sessions fabriqué à la main : (post_id, date, end_cause)."""
    return pd.DataFrame(
        {
            "post_id": [r[0] for r in rows],
            "site": "Park A",
            "start_time": pd.to_datetime([r[1] for r in rows]),
            "end_cause": [r[2] for r in rows],
            "energy_kwh": 10.0,
        }
    )


CAUSES = ["DC Output Fault"]


def test_hardware_fault_ignores_vehicle_causes():
    s = make_sessions([(1, "2020-01-01 10:00", "DC Output Fault"),
                       (1, "2020-01-01 11:00", "BMS failure")])
    s = add_hardware_fault(s, CAUSES)
    assert s["is_hw_fault"].tolist() == [1, 0]


def test_daily_table_fills_missing_days():
    s = make_sessions([(1, "2020-01-01 10:00", "DC Output Fault"),
                       (1, "2020-01-01 12:00", "Charging ends normally"),
                       (1, "2020-01-03 09:00", "Charging ends normally")])
    daily = daily_post_table(add_hardware_fault(s, CAUSES))

    assert daily["date"].dt.day.tolist() == [1, 2, 3]     # le 2 janvier est ajouté
    assert daily["n_sessions"].tolist() == [2, 0, 1]
    assert daily["n_hw_faults"].tolist() == [1, 0, 0]
    assert daily.loc[0, "hw_fault_rate"] == 0.5
    assert pd.isna(daily.loc[1, "hw_fault_rate"])         # un jour sans session n'a pas de taux


def test_baseline_uses_only_the_past():
    days = pd.date_range("2020-01-01", periods=10, freq="D")
    rows = [(1, f"{d.date()} 10:00", "Charging ends normally") for d in days[:-1]]
    rows.append((1, f"{days[-1].date()} 10:00", "DC Output Fault"))   # défaut le dernier jour
    daily = add_past_baseline(daily_post_table(add_hardware_fault(make_sessions(rows), CAUSES)))

    # le défaut du dernier jour ne doit pas entrer dans sa propre référence
    assert daily["baseline_rate"].iloc[-1] == 0.0

def test_label_episodes_rules():
    from evrel.target import label_episodes

    daily = pd.DataFrame({
        "n_sessions":    [10,   10,   0,    10,   10],
        "n_hw_faults":   [3,    1,    0,    3,    3],
        "hw_fault_rate": [0.3,  0.1,  None, 0.3,  0.3],
        "baseline_rate": [0.05, 0.05, 0.05, 0.2,  None],
    })
    out = label_episodes(daily, min_faults=2, min_ratio=2)["is_episode"].tolist()

    assert out[0] == 1            # 3 défauts, taux 6x l'habituel : épisode
    assert out[1] == 0            # 1 seul défaut : pas d'épisode
    assert pd.isna(out[2])        # aucune session : non observable
    assert out[3] == 0            # 3 défauts mais seulement 1,5x l'habituel : borne chroniquement mauvaise
    assert pd.isna(out[4])        # niveau habituel inconnu : non observable