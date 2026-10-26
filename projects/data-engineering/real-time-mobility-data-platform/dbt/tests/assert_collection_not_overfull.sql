{{ config(severity='warn') }}
-- AVERTISSEMENT : plus de relevés que prévu dans une heure = deux collecteurs lancés en même temps ?
-- On compare avec expected_snapshots (60 par heure, 120 pour l'heure qui existe deux fois lors du
-- passage à l'heure d'hiver), avec une marge de 1 relevé.
select *
from {{ ref('fct_collection_hourly') }}
where snapshots > expected_snapshots + 1
