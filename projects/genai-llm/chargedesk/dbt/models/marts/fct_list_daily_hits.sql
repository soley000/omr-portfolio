select
    evening,
    target_date,
    model,
    count(*)                                                      as n_listed,
    count(*) filter (where episode_next_day)                      as n_hits,
    count(*) filter (where episode_next_day is null)              as n_unknown,
    count(*) filter (where episode_next_day)
        / nullif(count(*) filter (where episode_next_day is not null), 0) as precision,
    target_date                                                   as outcome_known_from
from {{ ref('fct_evening_list') }}
group by evening, target_date, model