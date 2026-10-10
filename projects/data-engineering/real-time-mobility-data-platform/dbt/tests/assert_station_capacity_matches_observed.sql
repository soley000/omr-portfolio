{{ config(severity='warn') }}
-- AVERTISSEMENT : stations dont la capacité annoncée ne correspond pas à ce qu'on compte
-- réellement (écart constant à chaque relevé). Une ligne = une station à signaler dans le README.
select station_id, name, capacity_declared, capacity_observed
from {{ ref('dim_station') }}
where has_capacity_gap