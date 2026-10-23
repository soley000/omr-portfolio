select
    post_id,
    cast(date as date)                    as day,
    trim(site)                            as site,
    n_sessions,
    n_hw_faults,
    energy_kwh,
    {{ nan_to_null('hw_fault_rate') }}    as hw_fault_rate,
    {{ nan_to_null('baseline_rate') }}    as baseline_rate,
    ({{ nan_to_null('is_episode') }} = 1) as is_episode
from {{ source('raw', 'daily_target') }}