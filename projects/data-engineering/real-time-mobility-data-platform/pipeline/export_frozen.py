"""Cree l'export FIGE du tableau de bord : un petit fichier DuckDB (quelques Mo) avec seulement les tables
que l'appli lit, plus une table "export_meta" (chiffres de synthese). C'est ce fichier qui est publie sur
GitHub et lu par la demo en ligne. Lecture seule sur la vraie base.

Usage (depuis la racine du projet) :
    python pipeline\\export_frozen.py C:\\dev\\mobilityflow-data\\warehouse\\mobilityflow.duckdb
"""
import sys
from pathlib import Path

import duckdb

src = Path(sys.argv[1])
out_dir = Path("export")
out_dir.mkdir(exist_ok=True)
out = out_dir / "mobilityflow_frozen.duckdb"
if out.exists():
    out.unlink()

con = duckdb.connect(str(out))
con.execute(f"attach '{src.as_posix()}' as src (read_only)")
for t in ("dim_station", "fct_station_hour", "fct_collection_hourly", "fct_station_unchanged"):
    con.execute(f"create table {t} as select * from src.main.{t}")
con.execute("""
    create table export_meta as
    select count(*)                                                       as snapshots_rows,
           count(distinct station_id)                                     as stations,
           count(distinct date_paris)                                     as days,
           min(date_paris)                                                as first_date,
           max(date_paris)                                                as last_date,
           cast(timezone('Europe/Paris', min(snapshot_ts)) as timestamp)  as first_snapshot,
           cast(timezone('Europe/Paris', max(snapshot_ts)) as timestamp)  as last_snapshot
    from src.main.stg_station_status""")
con.execute("detach src")
for t in ("dim_station", "fct_station_hour", "fct_collection_hourly", "fct_station_unchanged", "export_meta"):
    print(f"{t:<24} {con.execute(f'select count(*) from {t}').fetchone()[0]:>8} lignes")
con.close()

# Les fichiers .duckdb sont ignores par Git : ce .gitignore LOCAL au dossier export autorise celui-ci.
(out_dir / ".gitignore").write_text("!mobilityflow_frozen.duckdb\n", encoding="ascii")
print(f"OK : {out} ({out.stat().st_size / 1e6:.1f} Mo)")
