-- Doit renvoyer 0 ligne : une seule ligne par station, jour et heure.
select station_id, date_paris, hour_paris, count(*) as n
from {{ ref('fct_station_hour') }}
group by 1, 2, 3
having count(*) > 1