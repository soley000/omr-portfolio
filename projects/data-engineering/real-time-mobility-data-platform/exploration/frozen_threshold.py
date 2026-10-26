"""Teste plusieurs seuils pour "station figee". Lecture seule.
Usage : python exploration\\frozen_threshold.py C:\\dev\\mobilityflow-data\\warehouse\\mobilityflow.duckdb
"""
import sys
import duckdb

db = sys.argv[1]
con = duckdb.connect(db, read_only=True)
total = con.sql("select count(*) from fct_station_unchanged where longest_unchanged_minutes is not null").fetchone()[0]
print(f"Stations avec au moins une periode : {total}\n")
print("Seuil   | stations dont la PLUS LONGUE periode depasse le seuil | figees A LA FIN de la collecte")
print("--------+-------------------------------------------------------+-------------------------------")
for h in (6, 8, 12, 18, 24, 36, 48):
    m = h * 60
    a, b = con.sql(
        f"select count(*) filter (where longest_unchanged_minutes >= {m}), "
        f"count(*) filter (where coalesce(current_unchanged_minutes,0) >= {m}) "
        "from fct_station_unchanged"
    ).fetchone()
    print(f"{h:>4} h  | {a:>53} | {b:>29}")
print("\nStations a la fin de la collecte, par duree sans changement (les 10 plus longues) :")
for sid, cur, lon in con.sql(
    "select station_id, current_unchanged_minutes, longest_unchanged_minutes "
    "from fct_station_unchanged where current_unchanged_minutes is not null "
    "order by current_unchanged_minutes desc limit 10").fetchall():
    print(f"  station {sid:>6} : en cours {cur/60:5.1f} h, record {lon/60:5.1f} h")
