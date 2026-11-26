"""End to end: one generate() call gives a connected, realistic set of tables."""

from datetime import date

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate


@pytest.fixture(scope="module")
def tables() -> dict[str, pd.DataFrame]:
    return generate(
        GeneratorConfig(seed=42, n_claims=20_000, months=18, start_date=date(2025, 1, 1))
    )


def test_every_foreign_key_resolves(tables: dict[str, pd.DataFrame]) -> None:
    claims, lines = tables["claims"], tables["claim_lines"]
    assert claims["patient_id"].isin(tables["patients"]["patient_id"]).all()
    assert claims["provider_id"].isin(tables["providers"]["provider_id"]).all()
    assert claims["payer_id"].isin(tables["payers"]["payer_id"]).all()
    assert tables["patients"]["payer_id"].isin(tables["payers"]["payer_id"]).all()
    assert lines["claim_id"].isin(claims["claim_id"]).all()
    assert claims["claim_id"].isin(lines["claim_id"]).all()


def test_patients_are_reused_across_claims(tables: dict[str, pd.DataFrame]) -> None:
    claims_per_patient = tables["claims"].groupby("patient_id").size()
    assert claims_per_patient.mean() > 1.5


def test_birth_years_are_plausible_for_the_service_window(tables: dict[str, pd.DataFrame]) -> None:
    years = tables["patients"]["birth_year"]
    assert years.between(1925, 2025).all()


def test_volume_is_spread_across_all_18_months(tables: dict[str, pd.DataFrame]) -> None:
    per_month = tables["claims"]["service_date"].dt.to_period("M").value_counts()
    assert len(per_month) == 18
    assert per_month.min() > 0.5 * per_month.mean()


def test_charges_have_realistic_spread(tables: dict[str, pd.DataFrame]) -> None:
    charges = tables["claims"]["total_charge"]
    assert 50 < charges.median() < 2_000
    assert charges.max() > 5 * charges.median()
