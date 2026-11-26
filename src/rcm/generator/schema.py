"""The agreed shape of every generated table: column -> type, in column order."""

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
}

PRIMARY_KEYS: dict[str, str] = {
    "payers": "payer_id",
    "providers": "provider_id",
    "patients": "patient_id",
    "claims": "claim_id",
    "claim_lines": "claim_line_id",
}
