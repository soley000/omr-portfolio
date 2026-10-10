-- Complétude de NOTRE collecte : combien de relevés par heure (60 attendus) ?
-- Une heure incomplète = collecteur arrêté ou PC en veille. La première et la dernière heure
-- de la période sont signalées "partielles" (normal : la collecte a démarré ou s'est arrêtée
-- en cours d'heure).
with per_hour as (
    select
        date_paris,
        cast(extract(hour from snapshot_paris) as integer)  as hour_paris,
        count(distinct snapshot_ts)                         as snapshots,
        min(snapshot_ts)                                    as first_ts,
        max(snapshot_ts)                                    as last_ts
    from {{ ref('stg_station_status') }}
    group by 1, 2
),

bounds as (
    select min(first_ts) as period_start, max(last_ts) as period_end from per_hour
)

select
    p.date_paris,
    p.hour_paris,
    p.snapshots,
    60                                          as expected_snapshots,
    greatest(60 - p.snapshots, 0)               as missing_snapshots,
    round(p.snapshots / 60.0, 3)                as completeness,
    (p.first_ts = b.period_start or p.last_ts = b.period_end) as is_partial_hour
from per_hour p
cross join bounds b