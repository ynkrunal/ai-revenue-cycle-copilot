"""The API's request schema stays in sync with the model's features and reference codes."""

import typing

import pytest
from pydantic import ValidationError

from rcm.api.schemas import ClaimFeatures, WorklistItem
from rcm.generator import reference
from rcm.models.features import FEATURES
from rcm.models.train import WORKLIST_COLUMNS

VALID = {
    "claim_id": "SYN-CLM-0000001",
    "payer_id": "SYN-PAY-0001",
    "payer_type": "commercial",
    "provider_specialty": "orthopedics",
    "provider_state": "MA",
    "place_of_service": "11",
    "primary_icd10": "M17.11",
    "primary_cpt_code": "73721",
    "patient_sex": "F",
    "timely_filing_days": 90,
    "line_count": 2,
    "distinct_cpt_count": 2,
    "total_units": 2,
    "total_charge": 1650.25,
    "max_line_charge": 1400.0,
    "days_to_submit": 4,
    "share_of_timely_limit_used": 0.044,
    "patient_age_at_service": 57,
    "requires_prior_auth": True,
    "prior_auth_obtained": False,
    "missing_prior_auth": True,
    "past_timely_filing_limit": False,
    "has_z_code_dx": False,
}


def _choices(field: str) -> set[str]:
    return set(typing.get_args(ClaimFeatures.model_fields[field].annotation))


def test_request_fields_are_exactly_the_model_features() -> None:
    assert set(ClaimFeatures.model_fields) == set(FEATURES) | {"claim_id"}


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("payer_type", reference.PAYER_TYPES),
        ("provider_specialty", set(reference.SPECIALTY_CPT)),
        ("place_of_service", set(reference.PLACES_OF_SERVICE)),
        ("patient_sex", reference.SEXES),
        ("provider_state", set(reference.STATES)),
    ],
)
def test_enumerated_fields_match_reference(field: str, expected: set[str]) -> None:
    assert _choices(field) == set(expected)


def test_a_valid_claim_parses() -> None:
    claim = ClaimFeatures(**VALID)
    assert claim.model_dump(exclude={"claim_id"}).keys() == set(FEATURES)


def test_claim_id_is_optional() -> None:
    ClaimFeatures(**{k: v for k, v in VALID.items() if k != "claim_id"})


@pytest.mark.parametrize(
    "bad",
    [
        {"total_charge": -1.0},
        {"line_count": 0},
        {"patient_age_at_service": 130},
        {"days_to_submit": -2},
        {"payer_type": "space_insurance"},
        {"timely_filing_days": 0},
    ],
)
def test_out_of_range_values_are_rejected(bad: dict) -> None:
    with pytest.raises(ValidationError):
        ClaimFeatures(**(VALID | bad))


@pytest.mark.parametrize("leak", ["paid_amount", "is_denied", "carc_code", "claim_status"])
def test_unknown_fields_are_rejected_so_outcomes_cannot_sneak_in(leak: str) -> None:
    with pytest.raises(ValidationError, match=leak):
        ClaimFeatures(**(VALID | {leak: 1}))


def test_worklist_item_matches_the_csv_columns() -> None:
    expected = ["rank", *WORKLIST_COLUMNS, "p_deny", "recoverability", "priority_score"]
    assert list(WorklistItem.model_fields) == expected
