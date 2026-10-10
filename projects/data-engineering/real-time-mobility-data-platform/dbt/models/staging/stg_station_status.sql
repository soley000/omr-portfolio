-- Un relevé = une station à un instant. Une ligne par (station_id, snapshot_ts).
-- Source : les Parquet de la couche 2. Ici on ajoute seulement des colonnes
-- "métier" simples ; les règles plus fines viendront dans les modèles suivants.
with src as (
    select *
    from read_parquet('{{ parquet_glob("station_status") }}', hive_partitioning = true, union_by_name = true)
)

select
    station_id,
    snapshot_ts,                                                    -- heure de collecte (UTC)
    timezone('Europe/Paris', snapshot_ts)           as snapshot_paris,  -- même heure, à l'heure de Paris
    cast(date_paris as date)                        as date_paris,
    num_bikes_available,
    num_bikes_disabled,
    num_docks_available,
    num_docks_disabled,
    bikes_mechanical,
    is_installed,
    is_renting,
    is_returning,
    source_last_updated,
    last_reported_at,                                               -- gardé pour information, NON fiable
    coalesce(is_installed and is_renting, false)    as is_in_service,
    coalesce(is_installed and is_renting, false) and num_bikes_available = 0 as is_empty,
    coalesce(is_installed and is_renting, false) and num_docks_available = 0 as is_full,
    coalesce(num_bikes_available, 0) + coalesce(num_bikes_disabled, 0)
      + coalesce(num_docks_available, 0) + coalesce(num_docks_disabled, 0)    as places_counted
from src