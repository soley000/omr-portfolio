"""Chiffres de gel de MobilityFlow, calcules sur l'entrepot publie (lecture seule).

Usage : python exploration\\freeze_figures.py [chemin_vers_mobilityflow.duckdb] [--from AAAA-MM-JJ] [--to AAAA-MM-JJ]
Les options --from et --to limitent la periode des sections "volume", "releves par jour" et "regle des 20 %".
Ne modifie rien. Peut tourner pendant que Airflow ou Streamlit lisent la base.
"""
import argparse
import duckdb

DEFAULT = r"C:\dev\mobilityflow-data\warehouse\mobilityflow.duckdb"
ap = argparse.ArgumentParser()
ap.add_argument("db", nargs="?", default=DEFAULT)
ap.add_argument("--from", dest="d_from", default="1900-01-01")
ap.add_argument("--to", dest="d_to", default="2999-12-31")
args = ap.parse_args()
con = duckdb.connect(args.db, read_only=True)
# Filtre de periode applique a stg_station_status (dates de Paris)
W = f"where date_paris between date '{args.d_from}' and date '{args.d_to}'"
if args.d_from != "1900-01-01" or args.d_to != "2999-12-31":
    print(f"[Periode limitee : du {args.d_from} au {args.d_to}]")


def one(sql):
    return con.sql(sql).fetchone()


def title(t):
    print(f"\n=== {t} ===")


title("Periode et volume")
d0, d1, ndays = one(f"select min(date_paris), max(date_paris), count(distinct date_paris) from stg_station_status {W}")
rows, snaps, nst = one(f"select count(*), count(distinct snapshot_ts), count(distinct station_id) from stg_station_status {W}")
print(f"Du {d0} au {d1} : {ndays} jours (jour de Paris)")
print(f"Mesures (une ligne par station et par minute) : {rows:,}".replace(",", " "))
print(f"Releves (minutes distinctes collectees)        : {snaps:,}".replace(",", " "))
print(f"Stations distinctes dans les mesures           : {nst}")

title("Releves par jour (1 440 attendus ; 1 500 le 25 octobre 2026, jour de 25 h)")
for d, n in con.sql(f"select date_paris, count(distinct snapshot_ts) from stg_station_status {W} group by 1 order by 1").fetchall():
    print(f"  {d} : {n}")

title("Completude de la collecte (hors premiere et derniere heures partielles)")
exp, got = one("select sum(expected_snapshots), sum(least(snapshots, expected_snapshots)) from fct_collection_hourly where not is_partial_hour")
print(f"  {got:,} releves sur {exp:,} attendus = {100*got/exp:.1f} %".replace(",", " "))
print("  (les heures sans aucun releve ne sont pas dans cette table : voir collection_gaps.py)")

title("Stations")
n, in_srv, gap = one("""
    select count(*), sum(cast(is_in_service_now as int)), sum(cast(has_capacity_gap as int)) from dim_station""")
frz = one("select sum(cast(looks_frozen_now as int)) from fct_station_unchanged")[0]
print(f"  Stations dans dim_station                : {n}")
print(f"  En service au dernier releve             : {in_srv}")
print(f"  Avec un ecart de capacite                : {gap}")
print(f"  Qui semblent figees au dernier releve    : {frz}")
bad = con.sql("select station_id, name, lat, lon from dim_station where lat = 0 and lon = 0").fetchall()
print(f"  Coordonnees en (0, 0)                    : {len(bad)} {[b[:2] for b in bad]}")
ni, nr = one("select sum(cast(not is_installed_now as int)), sum(cast(not is_renting_now as int)) from dim_station")
print(f"  Non installees / ne louent pas (dernier) : {ni} / {nr}")

title("Regle des 20 % : combien de stations sont signalees selon le seuil ?")
rows = con.sql(f"""
    with s as (
        select station_id,
               sum(cast(is_in_service as int))                                   as n_service,
               sum(cast(is_in_service and is_empty as int))                      as n_empty,
               sum(cast(is_in_service and is_full as int))                       as n_full
        from stg_station_status {W} group by 1
    ),
    p as (select station_id, n_empty * 1.0 / nullif(n_service, 0) as pe, n_full * 1.0 / nullif(n_service, 0) as pf from s)
    select t.th,
           sum(cast(coalesce(pe, 0) >= t.th or coalesce(pf, 0) >= t.th as int)) as stations,
           sum(cast(coalesce(pe, 0) >= t.th as int))                            as vides,
           sum(cast(coalesce(pf, 0) >= t.th as int))                            as pleines
    from p, (select unnest([0.10, 0.15, 0.20, 0.25, 0.30, 0.40]) as th) t
    group by 1 order by 1
""").fetchall()
print(f"  {'seuil':>6}{'stations':>10}{'vides':>8}{'pleines':>9}")
for th, s_, v, p_ in rows:
    th = float(th)
    mark = "  <- seuil actuel" if abs(th - 0.20) < 1e-9 else ""
    print(f"  {int(th*100):>5}%{s_:>10}{v:>8}{p_:>9}{mark}")

title("Stations figees : plus longue periode sans aucun changement (minutes)")
q = con.sql("""
    select count(*), min(longest_unchanged_minutes),
           quantile_cont(longest_unchanged_minutes, 0.5),
           quantile_cont(longest_unchanged_minutes, 0.9),
           max(longest_unchanged_minutes)
    from fct_station_unchanged""").fetchone()
print(f"  stations={q[0]}  min={q[1]:.0f}  mediane={q[2]:.0f}  p90={q[3]:.0f}  max={q[4]:.0f}")
print("  (a comparer au seuil 'figee' actuel dans dbt/models/marts/fct_station_unchanged.sql)")
