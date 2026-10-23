-- Variables d'explication d'une borne pour CHAQUE soir (92 bornes x tous les jours).
-- Calculees seulement a partir du passe (fenetres qui finissent le soir J, jour J compris),
-- donc connues le soir meme : available_from = evening.
-- Remplace fct_post_signals pour l'agent : cette table d'entrainement n'a une ligne que si
-- le lendemain est observable, et la simple presence d'une ligne revele donc le futur.
with d as (
    select post_id, site, day, n_sessions, n_hw_faults, is_episode
    from {{ ref('fct_post_day') }}
),

w as (
    select
        post_id,
        site,
        day                                                      as evening,
        n_hw_faults                                              as hw_faults_d0,
        sum(n_hw_faults) over w3                                 as hw_faults_3d,
        sum(n_hw_faults) over w7                                 as hw_faults_7d,
        sum(n_hw_faults) over w28                                as hw_faults_28d,
        n_sessions                                               as sessions_d0,
        sum(n_sessions) over w7                                  as sessions_7d,
        sum(n_sessions) over w28                                 as sessions_28d,
        sum(case when n_sessions = 0 then 1 else 0 end) over w7  as idle_days_7d,
        sum(case when is_episode then 1 else 0 end) over w28     as episodes_28d,
        case when is_episode then 1.0 else 0.0 end               as episode_d0,   -- 0 si non observable, comme ChargeTriage
        max(case when is_episode then day end) over (
            partition by post_id order by day
            range between unbounded preceding and current row)   as last_episode_day
    from d
    window
        w3  as (partition by post_id order by day range between interval 2 days preceding and current row),
        w7  as (partition by post_id order by day range between interval 6 days preceding and current row),
        w28 as (partition by post_id order by day range between interval 27 days preceding and current row)
)

select
    post_id,
    site,
    evening,
    hw_faults_d0,
    hw_faults_3d,
    hw_faults_7d,
    hw_faults_28d,
    hw_faults_7d::double / nullif(sessions_7d, 0)   as hw_rate_7d,
    hw_faults_28d::double / nullif(sessions_28d, 0) as hw_rate_28d,
    sessions_d0,
    sessions_7d,
    sessions_28d,
    idle_days_7d,
    episodes_28d,
    episode_d0,
    last_episode_day,
    least(coalesce(date_diff('day', last_episode_day, evening), 365), 365) as days_since_episode,  -- plafond 365, comme ChargeTriage
    evening                                         as available_from
from w
