-- Doit renvoyer 0 ligne : un même couple (station, instant) ne doit exister qu'une fois.
select station_id, snapshot_ts, count(*) as n
from {{ ref('stg_station_status') }}
group by 1, 2
having count(*) > 1