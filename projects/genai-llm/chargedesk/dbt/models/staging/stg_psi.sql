select
    "Unnamed: 0"                                           as feature,
    month,
    cast(strptime(month || '-01', '%Y-%m-%d') as date)     as month_start,
    psi
from (
    unpivot {{ source('raw', 'psi_by_month') }}
    on columns(* exclude ("Unnamed: 0"))
    into name month value psi
) as psi_long