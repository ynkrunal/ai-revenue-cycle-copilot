-- One row per service line on a claim.
with source as (
    select * from {{ source('raw', 'claim_lines') }}
)

select
    cast(claim_line_id as varchar)      as claim_line_id,
    cast(claim_id as varchar)           as claim_id,
    cast(line_number as integer)        as line_number,
    cast(cpt_code as varchar)           as cpt_code,
    cast(icd10_code as varchar)         as icd10_code,
    cast(units as integer)              as units,
    cast(line_charge as decimal(12, 2)) as line_charge
from source
