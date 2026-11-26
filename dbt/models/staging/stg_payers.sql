-- One row per synthetic payer (insurance company).
with source as (
    select * from {{ source('raw', 'payers') }}
)

select
    cast(payer_id as varchar)           as payer_id,
    cast(payer_name as varchar)         as payer_name,
    cast(payer_type as varchar)         as payer_type,
    cast(timely_filing_days as integer) as timely_filing_days
from source
