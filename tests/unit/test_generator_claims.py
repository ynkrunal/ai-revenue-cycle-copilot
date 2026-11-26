"""Business rules for claim headers and lines."""

from dataclasses import replace

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate, reference


def test_claim_count_matches_config(
    tables: dict[str, pd.DataFrame], small_config: GeneratorConfig
) -> None:
    assert len(tables["claims"]) == small_config.n_claims


def test_total_charge_equals_sum_of_lines(tables: dict[str, pd.DataFrame]) -> None:
    line_totals = tables["claim_lines"].groupby("claim_id")["line_charge"].sum().round(2)
    claims = tables["claims"].set_index("claim_id")
    pd.testing.assert_series_equal(
        claims["total_charge"].sort_index(),
        line_totals.reindex(claims.index).sort_index(),
        check_names=False,
    )


def test_line_count_and_numbering(tables: dict[str, pd.DataFrame]) -> None:
    lines = tables["claim_lines"]
    counts = lines.groupby("claim_id").size()
    claims = tables["claims"].set_index("claim_id")
    assert (counts.reindex(claims.index) == claims["line_count"]).all()
    assert claims["line_count"].between(1, reference.MAX_LINES_PER_CLAIM).all()
    expected = lines.groupby("claim_id").cumcount() + 1
    assert (lines["line_number"] == expected).all()


def test_money_and_units_are_positive(tables: dict[str, pd.DataFrame]) -> None:
    lines = tables["claim_lines"]
    assert (lines["line_charge"] > 0).all()
    assert (lines["units"] >= 1).all()
    assert (lines["line_charge"].round(2) == lines["line_charge"]).all()


def test_dates_fall_in_window_and_submission_follows_service(
    tables: dict[str, pd.DataFrame], small_config: GeneratorConfig
) -> None:
    claims = tables["claims"]
    start = pd.Timestamp(small_config.start_date)
    end = start + pd.DateOffset(months=small_config.months)
    assert (claims["service_date"] >= start).all()
    assert (claims["service_date"] < end).all()
    assert (claims["submission_date"] >= claims["service_date"]).all()
    lag = (claims["submission_date"] - claims["service_date"]).dt.days
    assert lag.max() <= reference.MAX_SUBMISSION_LAG_DAYS


def test_service_dates_cover_every_month(
    tables: dict[str, pd.DataFrame], small_config: GeneratorConfig
) -> None:
    months = tables["claims"]["service_date"].dt.to_period("M").nunique()
    assert months == small_config.months


def test_prior_auth_flags_follow_cpt_rules(tables: dict[str, pd.DataFrame]) -> None:
    lines = tables["claim_lines"]
    needs_auth = (
        lines["cpt_code"].isin(reference.AUTH_REQUIRED_CPT).groupby(lines["claim_id"]).any()
    )
    claims = tables["claims"].set_index("claim_id")
    assert (claims["requires_prior_auth"] == needs_auth.reindex(claims.index)).all()
    # Auth can only be "obtained" on claims that need it.
    assert not (claims["prior_auth_obtained"] & ~claims["requires_prior_auth"]).any()
    # Some, but not all, auth-required claims are missing auth (a Step 3 denial driver).
    required = claims[claims["requires_prior_auth"]]
    assert 0 < required["prior_auth_obtained"].mean() < 1


def test_claim_payer_is_the_patients_payer(tables: dict[str, pd.DataFrame]) -> None:
    patients = tables["patients"].set_index("patient_id")["payer_id"]
    claims = tables["claims"]
    assert (claims["payer_id"] == claims["patient_id"].map(patients)).all()


def test_cpt_codes_match_provider_specialty(tables: dict[str, pd.DataFrame]) -> None:
    specialty = tables["providers"].set_index("provider_id")["specialty"]
    lines = tables["claim_lines"].merge(
        tables["claims"][["claim_id", "provider_id"]], on="claim_id"
    )
    allowed = lines["provider_id"].map(specialty).map(reference.SPECIALTY_CPT)
    ok = [cpt in codes for cpt, codes in zip(lines["cpt_code"], allowed, strict=True)]
    assert all(ok)


def test_primary_icd_is_first_line_icd(tables: dict[str, pd.DataFrame]) -> None:
    first = tables["claim_lines"].query("line_number == 1").set_index("claim_id")["icd10_code"]
    claims = tables["claims"].set_index("claim_id")
    assert (claims["primary_icd10"] == first.reindex(claims.index)).all()


def test_has_a_mix_of_payer_types(tables: dict[str, pd.DataFrame]) -> None:
    payer_type = tables["payers"].set_index("payer_id")["payer_type"]
    used = set(tables["claims"]["payer_id"].map(payer_type))
    assert used == reference.PAYER_TYPES


@pytest.mark.parametrize(
    "overrides",
    [{"n_claims": 0}, {"months": 0}, {"n_providers": 0}, {"n_patients": 0}],
)
def test_invalid_config_is_rejected(small_config: GeneratorConfig, overrides: dict) -> None:
    with pytest.raises(ValueError):
        generate(replace(small_config, **overrides))
