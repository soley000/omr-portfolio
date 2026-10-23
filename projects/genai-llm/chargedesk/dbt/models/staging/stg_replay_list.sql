select
    cast(date as date)           as evening,
    cast(target_date as date)    as target_date,
    model,
    rank,
    post_id,
    trim(site)                   as site,
    score,
    ({{ nan_to_null('y') }} = 1) as episode_next_day,
    mean_score_all,
    n_posts
from {{ source('raw', 'replay_list') }}