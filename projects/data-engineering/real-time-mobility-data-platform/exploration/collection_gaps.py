"""Liste les heures de collecte incompletes, y compris celles qui n'ont AUCUN releve.

La table fct_collection_hourly ne contient que les heures ou il existe au moins un releve.
Ce script reconstruit toutes les heures entre la premiere et la derniere, puis compte ce qui manque.
Lecture seule : ne modifie rien. Usage : python exploration\\collection_gaps.py [chemin_vers_mobilityflow.duckdb]
"""
import sys
import duckdb

DEFAULT = r"C:\dev\mobilityflow-data\warehouse\mobilityflow.duckdb"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

con = duckdb.connect(path, read_only=True)
rows = con.sql("""
    with h as (
        select cast(date_paris as timestamp) + hour_paris * interval 1 hour as ts,
               snapshots, is_partial_hour
        from fct_collection_hourly
    ),
    bounds as (select min(ts) as a, max(ts) as b from h),
    spine as (select unnest(generate_series(a, b, interval 1 hour)) as ts from bounds)
    select s.ts                              as heure_paris,
           coalesce(h.snapshots, 0)          as releves,
           60 - coalesce(h.snapshots, 0)     as manquants,
           h.snapshots is null               as heure_absente_de_la_table,
           coalesce(h.is_partial_hour, false) as heure_partielle
    from spine s left join h using (ts)
    where coalesce(h.snapshots, 0) < 60
    order by s.ts
""").fetchall()

total_h = con.sql("select count(*) from fct_collection_hourly").fetchone()[0]
print(f"Heures presentes dans fct_collection_hourly : {total_h}")
print(f"Heures incompletes (moins de 60 releves) : {len(rows)}\n")
print(f"{'heure (Paris)':<20}{'releves':>8}{'manquants':>11}  remarque")
for ts, n, miss, absent, partial in rows:
    note = []
    if absent: note.append("ABSENTE de la table (aucun releve)")
    if partial: note.append("heure partielle (debut ou fin de periode)")
    print(f"{str(ts)[:16]:<20}{n:>8}{miss:>11}  {' ; '.join(note)}")
print(f"\nTotal de releves manquants : {sum(r[2] for r in rows)}")
