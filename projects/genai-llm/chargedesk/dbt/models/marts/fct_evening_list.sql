select
    evening,
    target_date,
    model,
    rank,
    post_id,
    site,
    score,
    episode_next_day,
    target_date as outcome_known_from,
    mean_score_all,
    n_posts
from {{ ref('stg_replay_list') }}