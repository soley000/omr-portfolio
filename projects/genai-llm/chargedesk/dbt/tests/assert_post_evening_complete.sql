-- Une ligne par borne et par jour : autant que fct_post_day, sans doublon
select 'total' as probleme, count(*) as n
from {{ ref('fct_post_evening') }}
having count(*) <> (select count(*) from {{ ref('fct_post_day') }})
union all
select 'doublon', count(*)
from {{ ref('fct_post_evening') }}
group by post_id, evening
having count(*) > 1
