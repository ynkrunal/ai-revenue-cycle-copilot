"""Which columns the model may use, and the Python-side join of features to labels.

Features come only from `main_marts.feat_claims_at_submission` (facts known on the send
date). The label comes from `main_marts.fct_claims`. They meet here, by claim_id.
"""

from pathlib import Path

import duckdb
import pandas as pd

from rcm.generator.schema import SCHEMAS

MARTS_SCHEMA = "main_marts"

CATEGORICAL: list[str] = [
    "payer_id",
    "payer_type",
    "provider_specialty",
    "provider_state",
    "place_of_service",
    "primary_icd10",
    "primary_cpt_code",
    "patient_sex",
]
NUMERIC: list[str] = [
    "timely_filing_days",
    "line_count",
    "distinct_cpt_count",
    "total_units",
    "total_charge",
    "max_line_charge",
    "days_to_submit",
    "share_of_timely_limit_used",
    "patient_age_at_service",
]
BOOLEAN: list[str] = [
    "requires_prior_auth",
    "prior_auth_obtained",
    "missing_prior_auth",
    "past_timely_filing_limit",
    "has_z_code_dx",
]
FEATURES: list[str] = CATEGORICAL + NUMERIC + BOOLEAN

LABEL = "is_denied"
EVAL_COLUMNS: list[str] = ["denied_amount"]  # used to score the worklist, never to train

# Anything known only after the payer answers. None of these may sit on the feature side.
OUTCOME_COLUMNS: frozenset[str] = frozenset(
    (set(SCHEMAS["remits"]) | set(SCHEMAS["remit_adjustments"]) | {LABEL, *EVAL_COLUMNS})
    - {"claim_id", "claim_line_id"}
    | {"primary_denial_carc", "denial_carc_group", "days_to_adjudicate"}
)


def join_features_and_labels(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """One row per claim: every feature column plus the integer label and eval columns."""
    leaked = sorted(set(features.columns) & OUTCOME_COLUMNS)
    if leaked:
        raise ValueError(f"outcome columns found on the feature side: {leaked}")
    for name, df in (("features", features), ("labels", labels)):
        if not df["claim_id"].is_unique:
            raise ValueError(f"duplicate claim_id in {name}")

    joined = features.merge(
        labels[["claim_id", LABEL, *EVAL_COLUMNS]],
        on="claim_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing = int((joined.pop("_merge") != "both").sum())
    if missing:
        raise ValueError(f"{missing} claims have no label in fct_claims")
    joined[LABEL] = joined[LABEL].astype(bool).astype("int64")
    return joined


def load_training_frame(db_path: Path) -> pd.DataFrame:
    """Read features and labels from DuckDB separately, then join them in Python."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        features = con.sql(f"select * from {MARTS_SCHEMA}.feat_claims_at_submission").df()
        labels = con.sql(
            f"select claim_id, {LABEL}, {', '.join(EVAL_COLUMNS)} from {MARTS_SCHEMA}.fct_claims"
        ).df()
    for column in NUMERIC:
        features[column] = features[column].astype("float64")
    for column in ("submission_date", "submission_month", "service_date"):
        features[column] = pd.to_datetime(features[column])
    labels["denied_amount"] = labels["denied_amount"].astype("float64")
    return join_features_and_labels(features, labels)
