"""Denial rate and planted denial drivers.

Driver flags are rebuilt here from the raw claim tables, independently of the
generator code, so these tests check the data and not the implementation.
"""

from datetime import date

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate, reference

MIN_LIFT = 1.5  # TASK.md asks for lift > 1; we demand a clearly visible signal.


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    """One row per claim: driver flags (from claim data) plus the remit label."""
    t = generate(GeneratorConfig(seed=11, n_claims=40_000, months=18, start_date=date(2025, 1, 1)))
    claims, lines, payers = t["claims"], t["claim_lines"], t["payers"].set_index("payer_id")

    mismatch_line = pd.Series(False, index=lines.index)
    for icd, cpts in reference.DX_PROCEDURE_MISMATCH.items():
        mismatch_line |= (lines["icd10_code"] == icd) & lines["cpt_code"].isin(cpts)
    mismatch = mismatch_line.groupby(lines["claim_id"]).any()

    lag = (claims["submission_date"] - claims["service_date"]).dt.days
    out = pd.DataFrame(
        {
            "claim_id": claims["claim_id"],
            "missing_prior_auth": claims["requires_prior_auth"] & ~claims["prior_auth_obtained"],
            "late_submission": lag > claims["payer_id"].map(payers["timely_filing_days"]),
            "dx_procedure_mismatch": claims["claim_id"].map(mismatch).astype(bool),
            "strict_payer": claims["payer_id"]
            .map(payers["payer_type"])
            .isin(reference.STRICT_PAYER_TYPES),
        }
    )
    remits = t["remits"].set_index("claim_id")
    out["is_denied"] = out["claim_id"].map(remits["claim_status"] != "paid")
    adj = t["remit_adjustments"]
    denial = adj[adj["carc_code"].isin(reference.DENIAL_CARC)]
    first = denial.drop_duplicates("remit_id").set_index("remit_id")["carc_code"]
    out["denial_carc"] = out["claim_id"].map(remits["remit_id"]).map(first)
    return out


DRIVERS = ["missing_prior_auth", "late_submission", "dx_procedure_mismatch", "strict_payer"]


def test_denial_rate_is_between_8_and_15_percent(frame: pd.DataFrame) -> None:
    assert 0.08 <= frame["is_denied"].mean() <= 0.15


@pytest.mark.parametrize("driver", DRIVERS)
def test_driver_has_lift(frame: pd.DataFrame, driver: str) -> None:
    flagged = frame[frame[driver]]
    assert len(flagged) >= 100, f"too few {driver} claims to measure lift"
    lift = flagged["is_denied"].mean() / frame.loc[~frame[driver], "is_denied"].mean()
    assert lift > MIN_LIFT, f"{driver} lift {lift:.2f}"


@pytest.mark.parametrize(
    ("driver", "carc"),
    [("missing_prior_auth", "197"), ("late_submission", "29"), ("dx_procedure_mismatch", "11")],
)
def test_driver_shows_up_as_its_carc(frame: pd.DataFrame, driver: str, carc: str) -> None:
    denied = frame[frame[driver] & frame["is_denied"]]
    assert (denied["denial_carc"] == carc).mean() > 0.5


def test_driver_carcs_never_appear_without_the_driver(frame: pd.DataFrame) -> None:
    for driver, carc in [
        ("missing_prior_auth", "197"),
        ("late_submission", "29"),
        ("dx_procedure_mismatch", "11"),
    ]:
        assert not ((frame["denial_carc"] == carc) & ~frame[driver]).any(), carc


def test_noise_denials_hit_claims_with_no_driver(frame: pd.DataFrame) -> None:
    clean = frame[~frame[DRIVERS].any(axis=1)]
    assert 0.01 < clean["is_denied"].mean() < 0.10
    assert set(clean.loc[clean["is_denied"], "denial_carc"]) <= reference.NOISE_DENIAL_CARC


def test_drivers_are_not_deterministic(frame: pd.DataFrame) -> None:
    for driver in ["missing_prior_auth", "dx_procedure_mismatch", "strict_payer"]:
        assert frame.loc[frame[driver], "is_denied"].mean() < 0.99, driver
