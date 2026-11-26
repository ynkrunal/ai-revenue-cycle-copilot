"""Feature list hygiene and the Python-side join of features to labels."""

import pandas as pd
import pytest

from rcm.generator.schema import SCHEMAS
from rcm.models.features import (
    BOOLEAN,
    CATEGORICAL,
    EVAL_COLUMNS,
    FEATURES,
    LABEL,
    NUMERIC,
    join_features_and_labels,
)

FEATURE_TABLE_COLUMNS = {
    "claim_id", "submission_date", "submission_month", "service_date", "payer_id", "payer_type",
    "timely_filing_days", "provider_id", "provider_specialty", "provider_state",
    "place_of_service", "primary_icd10", "primary_cpt_code", "line_count", "distinct_cpt_count",
    "total_units", "total_charge", "max_line_charge", "requires_prior_auth",
    "prior_auth_obtained", "missing_prior_auth", "days_to_submit", "past_timely_filing_limit",
    "share_of_timely_limit_used", "patient_age_at_service", "patient_sex", "has_z_code_dx",
}  # fmt: skip
REMIT_COLUMNS = set(SCHEMAS["remits"]) | set(SCHEMAS["remit_adjustments"])
OUTCOME_COLUMNS = {
    "is_denied", "claim_status", "primary_denial_carc", "denial_carc_group",
    "denied_amount", "paid_amount", "allowed_amount", "adjudication_date",
}  # fmt: skip


def test_feature_groups_do_not_overlap_and_make_up_features() -> None:
    groups = [set(CATEGORICAL), set(NUMERIC), set(BOOLEAN)]
    assert sum(len(g) for g in groups) == len(FEATURES) == len(set(FEATURES))
    assert set().union(*groups) == set(FEATURES)


def test_every_feature_comes_from_the_submission_time_table() -> None:
    assert set(FEATURES) <= FEATURE_TABLE_COLUMNS


def test_no_feature_is_a_remit_or_outcome_column() -> None:
    assert not set(FEATURES) & (REMIT_COLUMNS - {"claim_id", "claim_line_id"})
    assert not set(FEATURES) & OUTCOME_COLUMNS
    assert LABEL not in FEATURES
    assert not set(FEATURES) & set(EVAL_COLUMNS)


def test_ids_and_raw_dates_are_not_features() -> None:
    """IDs invite memorising; raw dates do not carry over to future months."""
    assert not set(FEATURES) & {"claim_id", "provider_id", "patient_id"}
    assert not set(FEATURES) & {"submission_date", "service_date", "submission_month"}


def test_no_dx_procedure_mismatch_feature() -> None:
    """Agreed decision: the model must learn the mismatch from codes, not a copied rule."""
    assert not [f for f in FEATURES if "mismatch" in f]


def _features(ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"claim_id": ids, "total_charge": [100.0] * len(ids)})


def _labels(ids: list[str], denied: list[bool]) -> pd.DataFrame:
    return pd.DataFrame({"claim_id": ids, "is_denied": denied, "denied_amount": [0.0] * len(ids)})


def test_join_matches_on_claim_id_and_makes_an_integer_label() -> None:
    joined = join_features_and_labels(
        _features(["A", "B", "C"]), _labels(["C", "A", "B"], [True, False, False])
    )
    assert list(joined["claim_id"]) == ["A", "B", "C"]
    assert list(joined[LABEL]) == [0, 0, 1]
    assert joined[LABEL].dtype.kind == "i"


def test_join_rejects_duplicate_claims() -> None:
    with pytest.raises(ValueError):
        join_features_and_labels(_features(["A", "A"]), _labels(["A"], [True]))


def test_join_rejects_claims_missing_a_label() -> None:
    with pytest.raises(ValueError, match="label"):
        join_features_and_labels(_features(["A", "B"]), _labels(["A"], [True]))


def test_join_rejects_labels_sneaking_into_features() -> None:
    feats = _features(["A"]).assign(paid_amount=[1.0])
    with pytest.raises(ValueError, match="paid_amount"):
        join_features_and_labels(feats, _labels(["A"], [True]))
