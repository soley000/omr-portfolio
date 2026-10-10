{{ config(severity='warn') }}
-- AVERTISSEMENT : plus de 61 relevés dans une heure = deux collecteurs lancés en même temps ?
select *
from {{ ref('fct_collection_hourly') }}
where snapshots > 61