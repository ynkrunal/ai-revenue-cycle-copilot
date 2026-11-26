-- KPI totals must add back up to fct_claims, and each month-payer pair must appear once.
with kpi as (
    select
        sum(claims)        as claims,
        sum(denied_claims) as denied_claims,
        sum(denied_amount) as denied_amount,
        sum(billed_amount) as billed_amount,
        count(*)           as kpi_rows,
        count(distinct (submission_month, payer_id)) as kpi_keys
    from {{ ref('mart_denial_kpis') }}
),

fct as (
    select
        count(*)                          as claims,
        sum(cast(is_denied as integer))   as denied_claims,
        sum(denied_amount)                as denied_amount,
        sum(total_charge)                 as billed_amount
    from {{ ref('fct_claims') }}
)

select kpi.*, fct.*
from kpi, fct
where kpi.claims <> fct.claims
   or kpi.denied_claims <> fct.denied_claims
   or kpi.denied_amount <> fct.denied_amount
   or kpi.billed_amount <> fct.billed_amount
   or kpi.kpi_rows <> kpi.kpi_keys
