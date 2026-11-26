-- One row per synthetic provider (clinic).
with source as (
    select * from {{ source('raw', 'providers') }}
)

select
    cast(provider_id as varchar)   as provider_id,
    cast(provider_name as varchar) as provider_name,
    cast(specialty as varchar)     as specialty,
    cast(state as varchar)         as state
from source
