-- depends_on: {{ ref('dim_post') }}
-- depends_on: {{ ref('dim_site') }}
-- Une dimension ne contient que des attributs fixes : toute autre colonne est une fuite possible
-- (ex. derniere recharge ou totaux calcules sur 2020-2021, donc futurs vus d'un soir donne).
select table_name, column_name
from information_schema.columns
where table_schema = 'marts'
  and (
       (table_name = 'dim_post' and column_name not in ('post_id', 'site', 'district', 'first_day'))
    or (table_name = 'dim_site' and column_name not in ('site', 'district', 'n_posts'))
  )
