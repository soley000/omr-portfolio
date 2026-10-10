"""Génère de FAUSSES données brutes au format GBFS (aucune donnée réelle).

Sert uniquement aux tests automatiques. Les fausses données contiennent des anomalies
VOLONTAIRES, pour vérifier que le pipeline les détecte :

  - station 4  : capacité annoncée (15) différente de ce qu'on compte (12)
  - station 5  : nombre de vélos figé pendant toute la période
  - station 9  : non installée (hors service)
  - station 11 : coordonnées GPS à (0, 0)
  - un trou de collecte le 2026-10-06 entre 08:10 et 08:49 (heure de Paris)
  - station 1 souvent vide le matin, station 2 souvent pleine le matin
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
UTC = ZoneInfo("UTC")

DAYS = ("2026-10-05", "2026-10-06", "2026-10-07")
START_HOUR, END_HOUR = 6, 12          # heures de Paris couvertes chaque jour
GAP_DAY, GAP_START, GAP_END = "2026-10-06", (8, 10), (8, 49)
N_STATIONS = 12
CAPACITIES = {1: 14, 2: 14, 3: 16, 4: 15, 5: 12, 6: 14, 7: 18, 8: 12, 9: 10, 10: 16, 11: 12, 12: 20}
REAL_CAPACITY = {**CAPACITIES, 4: 12}   # ce qu'on compte vraiment à la station 4


def _bikes(station: int, local: datetime) -> int:
    hour = local.hour + local.minute / 60
    cap = REAL_CAPACITY[station]
    if station == 1:
        return 0 if 7 <= hour < 9.5 else 3
    if station == 2:
        return cap if 7 <= hour < 9.5 else cap - 4
    if station == 5:
        return 7                                         # figée
    return max(0, min(cap, (station * 3 + local.minute // 10 + local.hour) % (cap + 1)))


def _status_payload(ts_utc: datetime, local: datetime) -> dict:
    stations = []
    for s in range(1, N_STATIONS + 1):
        installed = s != 9
        bikes = _bikes(s, local) if installed else 0
        cap = REAL_CAPACITY[s]
        stations.append({
            "station_id": str(s),
            "num_bikes_available": bikes,
            "num_bikes_disabled": 0,
            "num_docks_available": cap - bikes,
            "num_docks_disabled": 0,
            "is_installed": installed,
            "is_renting": installed,
            "is_returning": installed,
            "last_reported": int(ts_utc.timestamp()) - 86400,
            "vehicle_types_available": [{"vehicle_type_id": "mechanical", "count": bikes}],
        })
    return {"last_updated": int(ts_utc.timestamp()), "ttl": 1, "version": "2.3", "data": {"stations": stations}}


def _info_payload(ts_utc: datetime) -> dict:
    stations = []
    for s in range(1, N_STATIONS + 1):
        lat, lon = (0.0, 0.0) if s == 11 else (47.21 + s * 0.003, -1.55 - s * 0.002)
        stations.append({
            "station_id": str(s), "name": f"STATION {s}", "address": f"{s} rue de l'Exemple",
            "lat": lat, "lon": lon, "capacity": CAPACITIES[s], "rental_methods": ["CREDITCARD"],
        })
    return {"last_updated": int(ts_utc.timestamp()), "ttl": 21600, "version": "2.3", "data": {"stations": stations}}


def _write(raw_dir: Path, feed: str, ts_utc: datetime, payload: dict) -> None:
    folder = raw_dir / feed / f"date={ts_utc:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{ts_utc:%H%M%S}.json").write_text(json.dumps(payload), encoding="utf-8")


def minutes_per_day() -> int:
    """Nombre de relevés attendus un jour normal (sans trou)."""
    return (END_HOUR - START_HOUR) * 60


def gap_minutes() -> int:
    return (GAP_END[0] * 60 + GAP_END[1]) - (GAP_START[0] * 60 + GAP_START[1]) + 1


def build(data_dir: Path) -> None:
    """Écrit les fausses données brutes dans <data_dir>/gbfs/nantes/<flux>/date=.../HHMMSS.json."""
    raw = Path(data_dir) / "gbfs" / "nantes"
    for day in DAYS:
        first = datetime.fromisoformat(day).replace(hour=START_HOUR, tzinfo=PARIS)
        for k in range(minutes_per_day()):
            local = first + timedelta(minutes=k)
            if day == GAP_DAY and GAP_START <= (local.hour, local.minute) <= GAP_END:
                continue                                  # le collecteur était arrêté
            ts_utc = local.astimezone(UTC)
            _write(raw, "station_status", ts_utc, _status_payload(ts_utc, local))
            if k == 0:                                    # un référentiel par jour
                _write(raw, "station_information", ts_utc, _info_payload(ts_utc))


if __name__ == "__main__":
    import sys
    build(Path(sys.argv[1]))
    print("fausses données écrites dans", sys.argv[1])