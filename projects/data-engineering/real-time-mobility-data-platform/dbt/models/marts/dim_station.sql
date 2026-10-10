-- Une ligne par station : fiche d'identité + capacité annoncée ET observée + dernier état connu.
-- "capacité observée" = la somme vélos + places (dispo et hors service) qui revient le plus
-- souvent quand la station est installée. Elle sert pour les taux de remplissage, car la
-- capacité annoncée est fausse pour quelques stations (écart constant, voir README).
with observed as (
    select
        station_id,
        mode(places_counted) filter (where is_installed)  as capacity_observed,
        min(snapshot_ts)                                  as first_seen_ts,
        max(snapshot_ts)                                  as last_seen_ts
    from {{ ref('stg_station_status') }}
    group by station_id
),

latest as (
    select station_id, is_installed, is_renting, is_in_service
    from {{ ref('stg_station_status') }}
    qualify snapshot_ts = max(snapshot_ts) over ()
)

select
    i.station_id,
    i.name,
    i.address,
    i.lat,
    i.lon,
    i.capacity                                              as capacity_declared,
    coalesce(o.capacity_observed, i.capacity)               as capacity_observed,
    coalesce(o.capacity_observed <> i.capacity, false)      as has_capacity_gap,
    o.first_seen_ts,
    o.last_seen_ts,
    l.is_installed                                          as is_installed_now,
    l.is_renting                                            as is_renting_now,
    coalesce(l.is_in_service, false)                        as is_in_service_now
from {{ ref('stg_station_information') }} i
left join observed o using (station_id)
left join latest   l using (station_id)