-- LEAKAGE GUARD. Fails (returns rows) if the feature table has any column that comes from a
-- remit, or whose name looks like an adjudication outcome. Features must use only facts
-- known when the claim is submitted.
with feature_columns as (
    select column_name
    from information_schema.columns
    where table_schema = '{{ ref("feat_claims_at_submission").schema }}'
      and table_name = 'feat_claims_at_submission'
),

remit_columns as (
    select column_name
    from information_schema.columns
    where table_schema = '{{ ref("stg_remits").schema }}'
      and table_name in (
          '{{ ref("stg_remits").identifier }}',
          '{{ ref("stg_remit_adjustments").identifier }}'
      )
      and column_name not in ('claim_id', 'claim_line_id')
)

select column_name, 'column exists in a remit table' as reason
from feature_columns
where column_name in (select column_name from remit_columns)

union all

select column_name, 'name looks like an adjudication outcome' as reason
from feature_columns
where regexp_matches(
    column_name,
    'carc|rarc|remit|paid|allowed|adjudicat|denied|denial|claim_status|adjustment|responsibility'
)

union all

-- Fail loudly if the feature table is missing, instead of passing on zero columns.
select 'feat_claims_at_submission' as column_name, 'feature table not found' as reason
where not exists (select 1 from feature_columns)
