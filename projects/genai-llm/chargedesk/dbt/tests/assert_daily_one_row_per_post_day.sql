-- Une seule ligne par borne et par jour
select post_id, day, count(*) as n
from {{ ref('stg_daily') }}
group by post_id, day
having count(*) > 1