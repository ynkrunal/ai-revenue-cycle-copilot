-- One row per claim: facts about its service lines, all known at submission.
select
    claim_id,
    max(case when line_number = 1 then cpt_code end)       as primary_cpt_code,
    count(distinct cpt_code)                               as distinct_cpt_count,
    cast(sum(units) as integer)                            as total_units,
    max(line_charge)                                       as max_line_charge,
    bool_or(icd10_code like 'Z%')                          as has_z_code_dx
from {{ ref('stg_claim_lines') }}
group by claim_id
