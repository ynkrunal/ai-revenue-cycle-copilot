-- One row per claim: what the payer decided. LABELS ONLY: never join this into features.
with adjustments as (
    select
        a.adjustment_id,
        a.carc_code,
        a.adjustment_amount,
        r.claim_id
    from {{ ref('stg_remit_adjustments') }} as a
    inner join {{ ref('stg_remits') }} as r on a.remit_id = r.remit_id
),

denials as (
    select
        adjustments.*,
        c.carc_group
    from adjustments
    inner join {{ ref('carc_reference') }} as c on adjustments.carc_code = c.carc_code
    where c.is_denial
),

denial_summary as (
    select
        claim_id,
        arg_min(carc_code, adjustment_id)  as primary_denial_carc,
        arg_min(carc_group, adjustment_id) as denial_carc_group,
        sum(adjustment_amount)             as denied_amount
    from denials
    group by claim_id
)

select
    r.claim_id,
    r.remit_id,
    r.adjudication_date,
    r.claim_status,
    r.claim_status <> 'paid'                                  as is_denied,
    d.primary_denial_carc,
    d.denial_carc_group,
    cast(coalesce(d.denied_amount, 0) as decimal(12, 2))      as denied_amount,
    r.allowed_amount,
    r.paid_amount,
    r.patient_responsibility
from {{ ref('stg_remits') }} as r
left join denial_summary as d on r.claim_id = d.claim_id
