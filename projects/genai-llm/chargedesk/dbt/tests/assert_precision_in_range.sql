-- La precision d'une liste est toujours entre 0 et 1
select evening, model, precision
from {{ ref('fct_list_daily_hits') }}
where precision < 0 or precision > 1