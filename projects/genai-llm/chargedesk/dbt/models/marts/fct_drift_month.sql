select
    feature,
    month,
    month_start,
    psi,
    case
        when psi < 0.10 then 'stable'
        when psi <= 0.25 then 'watch'
        else 'drift'
    end                     as level,
    last_day(month_start)   as available_from
from {{ ref('stg_psi') }}