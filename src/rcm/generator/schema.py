"""The agreed shape of every generated table: column -> type, in column order.

Remit tables hold adjudication outcomes. They are used for labels only, never as features.
"""

SCHEMAS: dict[str, dict[str, str]] = {
    "payers": {
        "payer_id": "string",
        "payer_name": "string",
        "payer_type": "string",
        "timely_filing_days": "int",
    },
    "providers": {
        "provider_id": "string",
        "provider_name": "string",
        "specialty": "string",
        "state": "string",
    },
    "patients": {
        "patient_id": "string",
        "birth_year": "int",
        "sex": "string",
        "state": "string",
        "payer_id": "string",
    },
    "claims": {
        "claim_id": "string",
        "patient_id": "string",
        "provider_id": "string",
        "payer_id": "string",
        "service_date": "date",
        "submission_date": "date",
        "place_of_service": "string",
        "primary_icd10": "string",
        "requires_prior_auth": "bool",
        "prior_auth_obtained": "bool",
        "line_count": "int",
        "total_charge": "float",
    },
    "claim_lines": {
        "claim_line_id": "string",
        "claim_id": "string",
        "line_number": "int",
        "cpt_code": "string",
        "icd10_code": "string",
        "units": "int",
        "line_charge": "float",
    },
    "remits": {
        "remit_id": "string",
        "claim_id": "string",
        "adjudication_date": "date",
        "claim_status": "string",
        "allowed_amount": "float",
        "paid_amount": "float",
        "patient_responsibility": "float",
    },
    "remit_adjustments": {
        "adjustment_id": "string",
        "remit_id": "string",
        "claim_line_id": "string",
        "group_code": "string",
        "carc_code": "string",
        "rarc_code": "string",
        "adjustment_amount": "float",
    },
}

# Columns allowed to hold missing values (every other column must be filled).
NULLABLE_COLUMNS: dict[str, set[str]] = {
    "remit_adjustments": {"rarc_code"},
}

PRIMARY_KEYS: dict[str, str] = {
    "payers": "payer_id",
    "providers": "provider_id",
    "patients": "patient_id",
    "claims": "claim_id",
    "claim_lines": "claim_line_id",
    "remits": "remit_id",
    "remit_adjustments": "adjustment_id",
}
