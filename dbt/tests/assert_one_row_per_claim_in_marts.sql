-- fct_claims and feat_claims_at_submission must each have exactly one row per staged claim.
with counts as (
    select
        (select count(*) from {{ ref('stg_claims') }})                as staged,
        (select count(*) from {{ ref('fct_claims') }})                as fct,
        (select count(*) from {{ ref('feat_claims_at_submission') }}) as feat
)

select *
from counts
where fct <> staged or feat <> staged
