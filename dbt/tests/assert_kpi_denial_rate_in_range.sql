select submission_month, payer_id, denial_rate
from {{ ref('mart_denial_kpis') }}
where denial_rate < 0 or denial_rate > 1
