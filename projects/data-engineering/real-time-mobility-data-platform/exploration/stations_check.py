"""Controle des stations : combien existent, depuis quand, combien sont reellement en service.

Usage : python exploration\\stations_check.py [chemin_vers_mobilityflow.duckdb]
Lecture seule. Ne modifie rien.
"""
import sys
import duckdb

DEFAULT = r"C:\dev\mobilityflow-data\warehouse\mobilityflow.duckdb"
path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
con = duckdb.connect(path, read_only=True)


def title(t):
    print(f"\n=== {t} ===")


title("Par jour : stations vues et stations en service (moyenne par minute)")
print(f"  {'jour':<12}{'stations vues':>14}{'en service (moy.)':>19}{'installees (moy.)':>19}")
for d, seen, srv, inst in con.sql("""
    select date_paris,
           count(distinct station_id),
           sum(cast(is_in_service as int)) * 1.0 / count(distinct snapshot_ts),
           sum(cast(is_installed as int)) * 1.0 / count(distinct snapshot_ts)
    from stg_station_status group by 1 order by 1""").fetchall():
    print(f"  {str(d):<12}{seen:>14}{float(srv):>19.1f}{float(inst):>19.1f}")

title("Arrivee des stations : combien de stations vues pour la premiere fois, jour par jour")
for d, n in con.sql("""
    select cast(first_seen_ts as date), count(*) from dim_station group by 1 order by 1""").fetchall():
    print(f"  {d} : {n}")

title("Stations jamais en service sur toute la periode")
n_never = con.sql("""
    select count(*) from dim_station d
    where not exists (select 1 from stg_station_status s where s.station_id = d.station_id and s.is_in_service)
""").fetchone()[0]
print(f"  {n_never} stations n'ont jamais ete en service (installees et louant) d'apres les mesures")

title("Stations en service au dernier releve, par statut")
for lab, n in con.sql("""
    select case when is_in_service_now then 'en service'
                when not is_installed_now then 'non installee'
                when not is_renting_now then 'installee mais ne loue pas'
                else 'autre' end as statut, count(*)
    from dim_station group by 1 order by 2 desc""").fetchall():
    print(f"  {lab:<30}{n:>5}")

title("Dernier releve de la base")
ts, = con.sql("select cast(max(snapshot_ts) as varchar) from stg_station_status").fetchone()
print(f"  {ts}")
n_last = con.sql("select count(distinct station_id) from stg_station_status where snapshot_ts = (select max(snapshot_ts) from stg_station_status)").fetchone()[0]
print(f"  Stations presentes dans ce dernier releve : {n_last}")
