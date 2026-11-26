-- is_denied, claim_status and the denial reason must tell the same story.
select claim_id, claim_status, is_denied, primary_denial_carc, denied_amount
from {{ ref('fct_claims') }}
where is_denied <> (claim_status <> 'paid')
   or (is_denied and (primary_denial_carc is null or denied_amount <= 0))
   or (not is_denied and (primary_denial_carc is not null or denied_amount <> 0))
