-- One row per CAS adjustment on a remit line (CARC/RARC). Label source only.
with source as (
    select * from {{ source('raw', 'remit_adjustments') }}
)

select
    cast(adjustment_id as varchar)            as adjustment_id,
    cast(remit_id as varchar)                 as remit_id,
    cast(claim_line_id as varchar)            as claim_line_id,
    cast(group_code as varchar)               as group_code,
    cast(carc_code as varchar)                as carc_code,
    cast(rarc_code as varchar)                as rarc_code,
    cast(adjustment_amount as decimal(12, 2)) as adjustment_amount
from source
