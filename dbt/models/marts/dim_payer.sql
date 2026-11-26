select
    payer_id,
    payer_name,
    payer_type,
    timely_filing_days,
    payer_type in ('medicare', 'medicare_advantage', 'medicaid') as is_government_payer
from {{ ref('stg_payers') }}
