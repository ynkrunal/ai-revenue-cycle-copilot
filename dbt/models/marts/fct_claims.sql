-- One row per claim: the claim header joined to its first-remit outcome.
-- Holds the label (is_denied). Used for training labels, KPIs and the worklist; never as features.
select
    c.claim_id,
    c.patient_id,
    c.provider_id,
    c.payer_id,
    c.service_date,
    c.submission_date,
    cast(date_trunc('month', c.submission_date) as date)     as submission_month,
    o.adjudication_date,
    o.adjudication_date - c.submission_date                  as days_to_adjudicate,
    c.place_of_service,
    c.line_count,
    c.total_charge,
    o.claim_status,
    o.is_denied,
    o.primary_denial_carc,
    o.denial_carc_group,
    o.denied_amount,
    o.allowed_amount,
    o.paid_amount,
    o.patient_responsibility
from {{ ref('stg_claims') }} as c
inner join {{ ref('int_claim_outcomes') }} as o on c.claim_id = o.claim_id
