-- Le référentiel est recopié en entier à chaque rafraîchissement (toutes les 6 h).
-- On garde ici UNE ligne par station : la version la plus récente.
select
    station_id,
    name,
    address,
    lat,
    lon,
    capacity,
    rental_methods,
    snapshot_ts as info_snapshot_ts
from read_parquet('{{ parquet_glob("station_information") }}', hive_partitioning = true, union_by_name = true)
qualify row_number() over (partition by station_id order by snapshot_ts desc) = 1