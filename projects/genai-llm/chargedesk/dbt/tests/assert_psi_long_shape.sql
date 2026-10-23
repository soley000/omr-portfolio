-- 19 variables x 4 mois = 76 lignes
select count(*) as n
from {{ ref('stg_psi') }}
having count(*) <> 76