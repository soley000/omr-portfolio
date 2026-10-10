-- Doit renvoyer 0 ligne : aucun compteur négatif.
select *
from {{ ref('stg_station_status') }}
where num_bikes_available < 0 or num_bikes_disabled < 0
   or num_docks_available < 0 or num_docks_disabled < 0