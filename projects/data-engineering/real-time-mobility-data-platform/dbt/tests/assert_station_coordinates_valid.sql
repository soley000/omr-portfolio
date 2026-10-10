{{ config(severity = 'warn') }}
-- Stations dont les coordonnées GPS sont absentes, ou dont la latitude ou la longitude vaut 0 pile.
-- L'API renvoie parfois (0, 0) : la station est alors impossible à placer sur la carte.
-- Avertissement (pas une erreur) : on écarte ces stations de la carte, mais on les garde dans les calculs.
select station_id, name, lat, lon
from {{ ref('dim_station') }}
where lat is null or lon is null or lat = 0 or lon = 0