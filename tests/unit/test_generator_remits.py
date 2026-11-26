"""Remits (835-like): one first remit per claim, CARC/RARC adjustments that balance."""

import numpy as np
import pandas as pd

from rcm.generator import reference


def _denied_claim_ids(tables: dict[str, pd.DataFrame]) -> set[str]:
    adj = tables["remit_adjustments"]
    denial_adj = adj[adj["carc_code"].isin(reference.DENIAL_CARC)]
    remit_to_claim = tables["remits"].set_index("remit_id")["claim_id"]
    return set(denial_adj["remit_id"].map(remit_to_claim))


def test_every_claim_has_exactly_one_remit(tables: dict[str, pd.DataFrame]) -> None:
    remits = tables["remits"]
    assert remits["claim_id"].is_unique
    assert set(remits["claim_id"]) == set(tables["claims"]["claim_id"])


def test_adjudication_follows_submission(tables: dict[str, pd.DataFrame]) -> None:
    merged = tables["remits"].merge(tables["claims"], on="claim_id")
    days = (merged["adjudication_date"] - merged["submission_date"]).dt.days
    assert days.between(reference.MIN_ADJUDICATION_DAYS, reference.MAX_ADJUDICATION_DAYS).all()


def test_adjustments_point_at_lines_of_the_same_claim(tables: dict[str, pd.DataFrame]) -> None:
    adj = tables["remit_adjustments"].merge(
        tables["remits"][["remit_id", "claim_id"]], on="remit_id"
    )
    line_claim = tables["claim_lines"].set_index("claim_line_id")["claim_id"]
    assert (adj["claim_line_id"].map(line_claim) == adj["claim_id"]).all()


def test_money_balances_charge_equals_paid_plus_adjustments(
    tables: dict[str, pd.DataFrame],
) -> None:
    adj_total = tables["remit_adjustments"].groupby("remit_id")["adjustment_amount"].sum()
    remits = tables["remits"].set_index("remit_id")
    charge = remits["claim_id"].map(tables["claims"].set_index("claim_id")["total_charge"])
    balance = remits["paid_amount"] + adj_total.reindex(remits.index, fill_value=0.0)
    assert np.allclose(balance, charge, atol=0.05)


def test_paid_is_allowed_minus_patient_responsibility(tables: dict[str, pd.DataFrame]) -> None:
    r = tables["remits"]
    assert np.allclose(
        r["paid_amount"], r["allowed_amount"] - r["patient_responsibility"], atol=0.05
    )
    assert (r[["allowed_amount", "paid_amount", "patient_responsibility"]] >= 0).all().all()
    assert (tables["remit_adjustments"]["adjustment_amount"] > 0).all()


def test_status_matches_denial_carcs(tables: dict[str, pd.DataFrame]) -> None:
    remits = tables["remits"]
    denied_ids = _denied_claim_ids(tables)
    not_paid = set(remits.loc[remits["claim_status"] != "paid", "claim_id"])
    assert not_paid == denied_ids


def test_fully_denied_claims_pay_nothing(tables: dict[str, pd.DataFrame]) -> None:
    denied = tables["remits"].query("claim_status == 'denied'")
    assert len(denied) > 0
    assert (denied["paid_amount"] == 0).all()
    assert (denied["allowed_amount"] == 0).all()


def test_partial_denials_exist_and_pay_something(tables: dict[str, pd.DataFrame]) -> None:
    partial = tables["remits"].query("claim_status == 'partially_denied'")
    assert len(partial) > 0
    assert (partial["allowed_amount"] > 0).all()


def test_denial_adjustments_carry_the_full_line_charge(tables: dict[str, pd.DataFrame]) -> None:
    adj = tables["remit_adjustments"]
    denials = adj[adj["carc_code"].isin(reference.DENIAL_CARC)]
    charge = denials["claim_line_id"].map(
        tables["claim_lines"].set_index("claim_line_id")["line_charge"]
    )
    assert np.allclose(denials["adjustment_amount"], charge)
    # A denied line has one denial adjustment and nothing else.
    per_line = (
        adj[adj["claim_line_id"].isin(denials["claim_line_id"])].groupby("claim_line_id").size()
    )
    assert (per_line == 1).all()


def test_rarc_codes_follow_the_carc(tables: dict[str, pd.DataFrame]) -> None:
    adj = tables["remit_adjustments"]
    expected = adj["carc_code"].map(lambda c: reference.CARC_CODES[c].rarc)
    same = (adj["rarc_code"] == expected) | (adj["rarc_code"].isna() & expected.isna())
    assert same.all()


def test_group_codes(tables: dict[str, pd.DataFrame]) -> None:
    adj = tables["remit_adjustments"]
    patient_share = adj["carc_code"].isin(reference.PATIENT_RESPONSIBILITY_CARC)
    assert (adj.loc[patient_share, "group_code"] == "PR").all()
    assert (adj.loc[~patient_share, "group_code"] == "CO").all()


def test_claim_tables_carry_no_remit_fields(tables: dict[str, pd.DataFrame]) -> None:
    """Leakage guard: nothing known only after adjudication sits on claims or lines."""
    remit_only = {
        "carc_code",
        "rarc_code",
        "paid_amount",
        "allowed_amount",
        "claim_status",
        "adjudication_date",
        "patient_responsibility",
        "adjustment_amount",
        "group_code",
    }
    assert not remit_only & set(tables["claims"].columns)
    assert not remit_only & set(tables["claim_lines"].columns)
