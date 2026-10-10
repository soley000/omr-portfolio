-- Doit renvoyer 0 ligne : un pourcentage est toujours entre 0 et 1.
select *
from {{ ref('fct_station_hour') }}
where pct_empty not between 0 and 1
   or pct_full  not between 0 and 1
   or avg_fill_rate < 0