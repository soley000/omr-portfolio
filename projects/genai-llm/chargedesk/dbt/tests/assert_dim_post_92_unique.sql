-- 92 bornes, chacune une seule fois
select 'doublon' as probleme, post_id as valeur
from {{ ref('dim_post') }} group by post_id having count(*) > 1
union all
select 'total', count(*) from {{ ref('dim_post') }} having count(*) <> 92