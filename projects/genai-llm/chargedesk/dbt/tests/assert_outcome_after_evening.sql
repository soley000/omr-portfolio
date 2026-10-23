-- Anti-fuite : un resultat n'est jamais connu avant ou le soir ou on le predit
select 'fct_evening_list' as table_name, evening, outcome_known_from
from {{ ref('fct_evening_list') }} where outcome_known_from <= evening
union all
select 'fct_post_signals', evening, outcome_known_from
from {{ ref('fct_post_signals') }} where outcome_known_from <= evening