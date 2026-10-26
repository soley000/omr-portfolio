-- Completude de NOTRE collecte : combien de releves par heure (60 attendus) ?
-- Une heure incomplete = collecteur arrete ou PC en veille.
-- On part d'une LISTE D'HEURES complete (du premier au dernier releve), pas seulement des heures
-- qui ont des donnees : une heure sans aucun releve apparait donc avec 0 releve (60 manquants).
-- Les heures sont comptees en heure UTC puis regroupees en heure de Paris. Au passage a l'heure
-- d'hiver (25 oct 2026) l'heure locale 2 h existe deux fois : elle regroupe 2 heures UTC,
-- donc 120 releves attendus et non 60.
-- La premiere et la derniere heure de la periode sont signalees "partielles" (normal : la
-- collecte a demarre ou s'est arretee en cours d'heure).
with per_utc_hour as (
    select
        date_trunc('hour', snapshot_ts)  as utc_hour,
        count(distinct snapshot_ts)      as snapshots,
        min(snapshot_ts)                 as first_ts,
        max(snapshot_ts)                 as last_ts
    from {{ ref('stg_station_status') }}
    group by 1
),

bounds as (
    select min(first_ts) as period_start, max(last_ts) as period_end from per_utc_hour
),

spine as (
    select
        unnest(generate_series(date_trunc('hour', period_start), date_trunc('hour', period_end), interval 1 hour)) as utc_hour,
        period_start,
        period_end
    from bounds
),

joined as (
    select
        s.utc_hour,
        timezone('Europe/Paris', s.utc_hour)  as local_hour,
        coalesce(p.snapshots, 0)              as snapshots,
        p.first_ts,
        p.last_ts,
        s.period_start,
        s.period_end
    from spine s
    left join per_utc_hour p using (utc_hour)
)

select
    cast(local_hour as date)                                         as date_paris,
    cast(extract(hour from local_hour) as integer)                   as hour_paris,
    cast(sum(snapshots) as bigint)                                   as snapshots,
    cast(60 * count(*) as integer)                                   as expected_snapshots,
    cast(greatest(60 * count(*) - sum(snapshots), 0) as bigint)      as missing_snapshots,
    round(sum(snapshots) / (60.0 * count(*)), 3)                     as completeness,
    coalesce(bool_or(first_ts = period_start or last_ts = period_end), false) as is_partial_hour
from joined
group by 1, 2
