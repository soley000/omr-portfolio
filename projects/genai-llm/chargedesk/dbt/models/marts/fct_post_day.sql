select
    d.post_id,
    d.site,
    p.district,
    d.day,
    d.n_sessions,
    d.n_hw_faults,
    d.energy_kwh,
    d.hw_fault_rate,
    d.baseline_rate,
    d.is_episode,
    d.is_episode is not null as is_observable,
    d.day                    as available_from
from {{ ref('stg_daily') }} d
left join {{ ref('dim_post') }} p on p.post_id = d.post_id