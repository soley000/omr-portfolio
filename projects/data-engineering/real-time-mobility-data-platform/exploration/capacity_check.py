"""MobilityFlow - enquête sur l'avertissement « vélos + places ≠ capacité » (lecture seule).

Répond à : sur combien de relevés la règle est-elle fausse ? sur quelles stations ?
de combien ? et quelle formule colle le mieux à la capacité annoncée ?

À lancer APRÈS `dbt run` (la base doit exister), et quand dbt n'est pas en cours d'exécution.

Usage :
    python capacity_check.py --data C:\\dev\\mobilityflow-data
"""
import argparse
from pathlib import Path

import duckdb

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
args = parser.parse_args()

db = Path(args.data) / "warehouse" / "mobilityflow.duckdb"
con = duckdb.connect(str(db), read_only=True)

BASE = """
    from stg_station_status s
    join stg_station_information i using (station_id)
    where s.is_installed and i.capacity is not null
"""

print("=== 1. Ampleur du problème (stations installées) ===")
con.sql(f"""
    select count(*) as releves_testes,
           count(*) filter (where s.places_counted <> i.capacity) as ecarts,
           round(100.0 * count(*) filter (where s.places_counted <> i.capacity) / count(*), 2) as pct
    {BASE}
""").show()

print("=== 2. Quelle formule colle à la capacité ? (nombre de relevés où elle est FAUSSE) ===")
con.sql(f"""
    select
      count(*) filter (where s.num_bikes_available + s.num_bikes_disabled
                             + s.num_docks_available + s.num_docks_disabled <> i.capacity) as velos_dispo_hs_places_dispo_hs,
      count(*) filter (where s.num_bikes_available + s.num_docks_available <> i.capacity)  as velos_dispo_places_dispo,
      count(*) filter (where s.num_bikes_available + s.num_bikes_disabled
                             + s.num_docks_available <> i.capacity)                          as velos_dispo_hs_places_dispo
    {BASE}
""").show()

print("=== 3. Répartition des écarts (places_counted - capacité) ===")
con.sql(f"""
    select s.places_counted - i.capacity as ecart, count(*) as releves
    {BASE} and s.places_counted <> i.capacity
    group by 1 order by releves desc limit 12
""").show()

print("=== 4. Stations les plus concernées ===")
con.sql(f"""
    select s.station_id, any_value(i.name) as nom, any_value(i.capacity) as capacite,
           count(*) as releves_en_ecart,
           min(s.places_counted) as min_compte, max(s.places_counted) as max_compte
    {BASE} and s.places_counted <> i.capacity
    group by 1 order by releves_en_ecart desc limit 15
""").show()