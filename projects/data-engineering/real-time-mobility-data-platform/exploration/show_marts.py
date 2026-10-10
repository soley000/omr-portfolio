"""MobilityFlow - affiche un aperçu des tables d'analyse créées par dbt (lecture seule).

À lancer après `dbt run`, quand dbt n'est pas en cours d'exécution.

Usage :
    python show_marts.py --data C:\\dev\\mobilityflow-data
"""
import argparse
from pathlib import Path

import duckdb

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
args = parser.parse_args()

con = duckdb.connect(str(Path(args.data) / "warehouse" / "mobilityflow.duckdb"), read_only=True)


def show(title, sql):
    print(f"\n=== {title} ===")
    con.sql(sql).show(max_width=200, max_rows=20)


show("Tables disponibles",
     "select table_name, table_type from information_schema.tables where table_schema='main' order by 1")

show("1. dim_station : les stations dont la capacité annoncée est fausse",
     """select station_id, name, capacity_declared, capacity_observed
        from dim_station where has_capacity_gap order by station_id""")

show("2. fct_collection_hourly : heures où la collecte est incomplète (hors 1re et dernière heure)",
     """select date_paris, hour_paris, snapshots, missing_snapshots, completeness
        from fct_collection_hourly
        where completeness < 0.95 and not is_partial_hour
        order by date_paris, hour_paris""")

show("3. fct_station_hour : les 10 stations le plus souvent vides (toutes heures confondues)",
     """select h.station_id, d.name, round(avg(h.pct_empty), 3) as pct_empty_moyen,
               round(avg(h.pct_full), 3) as pct_full_moyen
        from fct_station_hour h join dim_station d using (station_id)
        where h.snapshots_in_service > 0
        group by 1, 2 order by pct_empty_moyen desc limit 10""")

show("4. fct_station_hour : profil du réseau par heure de la journée (Paris)",
     """select hour_paris, round(avg(pct_empty), 3) as pct_vide, round(avg(pct_full), 3) as pct_plein,
               round(avg(avg_fill_rate), 3) as remplissage_moyen
        from fct_station_hour where snapshots_in_service > 0
        group by 1 order by 1""")

show("5. fct_station_unchanged : les 10 stations avec la plus longue période sans changement",
     """select u.station_id, d.name, u.longest_unchanged_minutes as plus_longue_min,
               u.current_unchanged_minutes as en_cours_min, u.looks_frozen_now
        from fct_station_unchanged u join dim_station d using (station_id)
        order by u.longest_unchanged_minutes desc nulls last limit 10""")