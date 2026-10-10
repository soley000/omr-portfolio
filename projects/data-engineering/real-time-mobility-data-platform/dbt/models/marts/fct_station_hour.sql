-- Une ligne par station, par jour (Paris) et par heure (Paris).
-- Répond à : "quelles stations sont souvent vides ou pleines, et à quelle heure ?"
-- Les pourcentages sont calculés sur les relevés où la station est EN SERVICE.
with s as (
    select
        st.*,
        d.capacity_observed
    from {{ ref('stg_station_status') }} st
    join {{ ref('dim_station') }} d using (station_id)
)

select
    station_id,
    date_paris,
    cast(extract(hour from snapshot_paris) as integer)                                   as hour_paris,
    count(*)                                                                             as snapshots,
    count(*) filter (where is_in_service)                                                as snapshots_in_service,
    round(avg(num_bikes_available) filter (where is_in_service), 2)                      as avg_bikes,
    min(num_bikes_available) filter (where is_in_service)                                as min_bikes,
    max(num_bikes_available) filter (where is_in_service)                                as max_bikes,
    round(count(*) filter (where is_empty) * 1.0
          / nullif(count(*) filter (where is_in_service), 0), 3)                         as pct_empty,
    round(count(*) filter (where is_full) * 1.0
          / nullif(count(*) filter (where is_in_service), 0), 3)                         as pct_full,
    round(avg(num_bikes_available * 1.0 / nullif(capacity_observed, 0))
          filter (where is_in_service), 3)                                               as avg_fill_rate
from s
group by station_id, date_paris, hour_paris