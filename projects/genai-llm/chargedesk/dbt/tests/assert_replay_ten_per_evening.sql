-- Chaque soir et chaque modele : exactement 10 bornes, rangs 1 a 10
select evening, model, count(*) as n, min(rank) as rank_min, max(rank) as rank_max
from {{ ref('stg_replay_list') }}
group by evening, model
having count(*) <> 10 or min(rank) <> 1 or max(rank) <> 10