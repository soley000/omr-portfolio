-- Une ligne par station : la plus longue période où ni le nombre de vélos ni le nombre de places
-- n'ont changé (station EN SERVICE), et la période en cours.
-- C'est un SIGNAL, pas un diagnostic : on ne peut pas distinguer une panne de capteur d'une
-- station simplement inactive. Le seuil est exploratoire (variable frozen_threshold_hours).
-- Un trou de collecte (> max_gap_minutes) interrompt une période : on ne compte pas ce qu'on n'a pas vu.
with s as (
    select station_id, snapshot_ts, num_bikes_available as bikes, num_docks_available as docks
    from {{ ref('stg_station_status') }}
    where is_in_service
),

flagged as (
    select
        *,
        case
            when bikes is distinct from lag(bikes) over w
              or docks is distinct from lag(docks) over w
              or snapshot_ts - lag(snapshot_ts) over w > interval '{{ var("max_gap_minutes") }} minutes'
              or lag(snapshot_ts) over w is null
            then 1 else 0
        end as is_new_period
    from s
    window w as (partition by station_id order by snapshot_ts)
),

numbered as (
    select *, sum(is_new_period) over (partition by station_id order by snapshot_ts rows unbounded preceding) as period_id
    from flagged
),

periods as (
    select
        station_id,
        period_id,
        min(snapshot_ts) as start_ts,
        max(snapshot_ts) as end_ts,
        date_diff('minute', min(snapshot_ts), max(snapshot_ts)) as minutes
    from numbered
    group by 1, 2
),

last_ts as (select max(snapshot_ts) as dataset_end from {{ ref('stg_station_status') }}),

ranked as (
    select
        p.*,
        row_number() over (partition by station_id order by minutes desc, start_ts) as rk_longest,
        p.end_ts = l.dataset_end as is_ongoing
    from periods p
    cross join last_ts l
)

select
    station_id,
    max(minutes) filter (where rk_longest = 1)   as longest_unchanged_minutes,
    max(start_ts) filter (where rk_longest = 1)  as longest_unchanged_start_ts,
    max(minutes) filter (where is_ongoing)       as current_unchanged_minutes,
    coalesce(max(minutes) filter (where is_ongoing) >= {{ var("frozen_threshold_hours") }} * 60, false)
                                                 as looks_frozen_now
from ranked
group by station_id