select
    provider_id,
    provider_name,
    specialty,
    state
from {{ ref('stg_providers') }}
