select
    post_id,
    site,
    alert_date,
    last_session_date,
    date_diff('day', last_session_date, alert_date) as days_silent,
    alert_date                                      as available_from
from {{ ref('stg_silent_posts') }}