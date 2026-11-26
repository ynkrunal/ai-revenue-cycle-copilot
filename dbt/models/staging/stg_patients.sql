-- One row per synthetic patient. Coarse attributes only: no name, DOB or SSN.
with source as (
    select * from {{ source('raw', 'patients') }}
)

select
    cast(patient_id as varchar) as patient_id,
    cast(birth_year as integer) as birth_year,
    cast(sex as varchar)        as sex,
    cast(state as varchar)      as state,
    cast(payer_id as varchar)   as payer_id
from source
