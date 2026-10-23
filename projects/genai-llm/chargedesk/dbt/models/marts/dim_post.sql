-- Attributs fixes d'une borne. Rien de date ici : tout ce qui depend du temps
-- (derniere recharge, totaux) se calcule depuis fct_post_day jusqu'au soir courant.
with posts as (
    select post_id, site, min(day) as first_day
    from {{ ref('stg_daily') }}
    group by post_id, site
),

districts as (
    select distinct post_id, district
    from {{ ref('stg_features') }}
)

select p.post_id, p.site, d.district, p.first_day
from posts p
left join districts d on d.post_id = p.post_id
