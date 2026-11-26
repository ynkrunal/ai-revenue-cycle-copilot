-- One row per claim header (837-like). Fields known at submission.
with source as (
    select * from {{ source('raw', 'claims') }}
)

select
    cast(claim_id as varchar)            as claim_id,
    cast(patient_id as varchar)          as patient_id,
    cast(provider_id as varchar)         as provider_id,
    cast(payer_id as varchar)            as payer_id,
    cast(service_date as date)           as service_date,
    cast(submission_date as date)        as submission_date,
    cast(place_of_service as varchar)    as place_of_service,
    cast(primary_icd10 as varchar)       as primary_icd10,
    cast(requires_prior_auth as boolean) as requires_prior_auth,
    cast(prior_auth_obtained as boolean) as prior_auth_obtained,
    cast(line_count as integer)          as line_count,
    cast(total_charge as decimal(12, 2)) as total_charge
from source
