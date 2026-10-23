-- Les variables recalculees doivent etre identiques a celles de ChargeTriage
-- sur tous les soirs ou les deux existent (56 673).
select s.post_id, s.evening
from {{ ref('fct_post_signals') }} s
join {{ ref('fct_post_evening') }} e on e.post_id = s.post_id and e.evening = s.evening
where e.hw_faults_d0  is distinct from s.hw_faults_d0
   or e.hw_faults_3d  is distinct from s.hw_faults_3d
   or e.hw_faults_7d  is distinct from s.hw_faults_7d
   or e.hw_faults_28d is distinct from s.hw_faults_28d
   or e.sessions_d0   is distinct from s.sessions_d0
   or e.sessions_7d   is distinct from s.sessions_7d
   or e.sessions_28d  is distinct from s.sessions_28d
   or e.idle_days_7d  is distinct from s.idle_days_7d
   or e.episodes_28d  is distinct from s.episodes_28d
   or e.episode_d0    is distinct from s.episode_d0
   or e.days_since_episode is distinct from s.days_since_episode
   or abs(e.hw_rate_7d  - s.hw_rate_7d)  > 1e-9
   or abs(e.hw_rate_28d - s.hw_rate_28d) > 1e-9
   or (e.hw_rate_7d  is null) <> (s.hw_rate_7d  is null)
   or (e.hw_rate_28d is null) <> (s.hw_rate_28d is null)
