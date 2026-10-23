select
    site,
    any_value(district) as district,
    count(*)            as n_posts
from {{ ref('dim_post') }}
group by site