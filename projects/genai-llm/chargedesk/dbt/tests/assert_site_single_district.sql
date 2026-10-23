-- Un seul district par site
select site, count(distinct district) as n_districts
from {{ ref('dim_post') }}
group by site
having count(distinct district) <> 1