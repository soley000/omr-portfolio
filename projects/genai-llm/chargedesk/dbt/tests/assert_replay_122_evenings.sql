-- Le rejeu couvre 122 soirs
select count(distinct evening) as n_evenings
from {{ ref('stg_replay_list') }}
having count(distinct evening) <> 122