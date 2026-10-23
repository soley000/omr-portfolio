select
    * exclude (date, target_date, y, site),
    trim(site)                   as site,
    cast(date as date)           as evening,
    cast(target_date as date)    as target_date,
    ({{ nan_to_null('y') }} = 1) as episode_next_day
from {{ source('raw', 'features') }}