-- One row per submission month and payer: volume, denial rate, dollars and the top denial reason.
with claims as (
    select * from {{ ref('fct_claims') }}
),

reason_counts as (
    select
        submission_month,
        payer_id,
        primary_denial_carc,
        denial_carc_group,
        count(*) as n,
        row_number() over (
            partition by submission_month, payer_id
            order by count(*) desc, primary_denial_carc
        ) as rank
    from claims
    where is_denied
    group by submission_month, payer_id, primary_denial_carc, denial_carc_group
),

totals as (
    select
        submission_month,
        payer_id,
        count(*)                                   as claims,
        cast(sum(cast(is_denied as integer)) as integer) as denied_claims,
        sum(total_charge)                          as billed_amount,
        sum(denied_amount)                         as denied_amount,
        sum(paid_amount)                           as paid_amount
    from claims
    group by submission_month, payer_id
)

select
    t.submission_month,
    t.payer_id,
    p.payer_type,
    t.claims,
    t.denied_claims,
    t.denied_claims / t.claims                     as denial_rate,
    t.billed_amount,
    t.denied_amount,
    t.paid_amount,
    r.primary_denial_carc                          as top_denial_carc,
    r.denial_carc_group                            as top_denial_carc_group
from totals as t
inner join {{ ref('dim_payer') }} as p on t.payer_id = p.payer_id
left join reason_counts as r
    on t.submission_month = r.submission_month
    and t.payer_id = r.payer_id
    and r.rank = 1
