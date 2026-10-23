-- Jours observables de la table quotidienne = lignes de la table des variables (56 673)
select *
from (
    select
        (select count(*) from {{ ref('fct_post_day') }} where is_observable) as observable_days,
        (select count(*) from {{ ref('fct_post_signals') }})                 as signal_rows
) as counts
where observable_days <> signal_rows