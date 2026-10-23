select
    post_id,
    cast(date as date)         as alert_date,
    cast(last_session as date) as last_session_date,
    trim(site)                 as site
from {{ source('raw', 'silent_posts') }}