-- Model features: one row per claim, using ONLY facts known when the claim is submitted.
-- Never ref a remit model here. tests/assert_no_remit_columns_in_features.sql and the
-- pytest lineage check enforce this.
with features as (
    select
        c.claim_id,
        c.submission_date,
        cast(date_trunc('month', c.submission_date) as date)            as submission_month,
        c.service_date,
        c.payer_id,
        p.payer_type,
        p.timely_filing_days,
        c.provider_id,
        pr.specialty                                                    as provider_specialty,
        pr.state                                                        as provider_state,
        c.place_of_service,
        c.primary_icd10,
        l.primary_cpt_code,
        c.line_count,
        l.distinct_cpt_count,
        l.total_units,
        c.total_charge,
        l.max_line_charge,
        c.requires_prior_auth,
        c.prior_auth_obtained,
        c.requires_prior_auth and not c.prior_auth_obtained             as missing_prior_auth,
        c.submission_date - c.service_date                              as days_to_submit,
        c.submission_date - c.service_date > p.timely_filing_days       as past_timely_filing_limit,
        (c.submission_date - c.service_date) / p.timely_filing_days     as share_of_timely_limit_used,
        cast(year(c.service_date) - pt.birth_year as integer)           as patient_age_at_service,
        pt.sex                                                          as patient_sex,
        l.has_z_code_dx
    from {{ ref('stg_claims') }} as c
    inner join {{ ref('stg_payers') }} as p on c.payer_id = p.payer_id
    inner join {{ ref('stg_providers') }} as pr on c.provider_id = pr.provider_id
    inner join {{ ref('stg_patients') }} as pt on c.patient_id = pt.patient_id
    inner join {{ ref('int_claim_line_summary') }} as l on c.claim_id = l.claim_id
)

select *
from features
