select
    *,
    target_date as outcome_known_from
from {{ ref('stg_features') }}