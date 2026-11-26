-- One row per claim: the payer's first remit (835-like). Label source only.
with source as (
    select * from {{ source('raw', 'remits') }}
)

select
    cast(remit_id as varchar)                      as remit_id,
    cast(claim_id as varchar)                      as claim_id,
    cast(adjudication_date as date)                as adjudication_date,
    cast(claim_status as varchar)                  as claim_status,
    cast(allowed_amount as decimal(12, 2))         as allowed_amount,
    cast(paid_amount as decimal(12, 2))            as paid_amount,
    cast(patient_responsibility as decimal(12, 2)) as patient_responsibility
from source
