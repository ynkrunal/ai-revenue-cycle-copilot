"""Priority score = P(deny) x balance x recoverability, and the ranked worklist."""

import numpy as np
import pandas as pd
import pytest

from rcm.models.priority import build_worklist, priority_score


def test_priority_is_the_product() -> None:
    got = priority_score(np.array([0.5, 0.1]), np.array([1000.0, 200.0]), np.array([1.0, 0.5]))
    assert np.allclose(got, [500.0, 10.0])


def test_recoverability_defaults_to_one() -> None:
    assert np.allclose(priority_score(np.array([0.2]), np.array([50.0])), [10.0])


@pytest.mark.parametrize(
    ("p", "balance", "recoverability"),
    [([1.2], [10.0], [1.0]), ([-0.1], [10.0], [1.0]), ([0.5], [-1.0], [1.0]),
     ([0.5], [10.0], [1.5]), ([np.nan], [10.0], [1.0])],
)  # fmt: skip
def test_invalid_inputs_are_rejected(p: list, balance: list, recoverability: list) -> None:
    with pytest.raises(ValueError):
        priority_score(np.array(p), np.array(balance), np.array(recoverability))


def _claims() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "claim_id": ["SYN-CLM-1", "SYN-CLM-2", "SYN-CLM-3", "SYN-CLM-4"],
            "p_deny": [0.90, 0.05, 0.30, 0.30],
            "total_charge": [100.0, 5000.0, 1000.0, 1000.0],
        }
    )


def test_worklist_is_sorted_by_expected_dollars_at_risk() -> None:
    wl = build_worklist(_claims())
    # 0.05 x 5000 = 250 and 0.30 x 1000 = 300 both beat 0.90 x 100 = 90.
    assert list(wl["claim_id"]) == ["SYN-CLM-3", "SYN-CLM-4", "SYN-CLM-2", "SYN-CLM-1"]
    assert wl["priority_score"].is_monotonic_decreasing
    assert list(wl["rank"]) == [1, 2, 3, 4]


def test_high_dollar_low_risk_can_outrank_low_dollar_high_risk() -> None:
    wl = build_worklist(_claims()).set_index("claim_id")
    assert wl.loc["SYN-CLM-2", "rank"] < wl.loc["SYN-CLM-1", "rank"]


def test_ties_break_by_claim_id_so_order_is_stable() -> None:
    shuffled = _claims().sample(frac=1.0, random_state=3)
    assert list(build_worklist(shuffled)["claim_id"]) == list(build_worklist(_claims())["claim_id"])


def test_worklist_keeps_inputs_and_adds_score_columns() -> None:
    wl = build_worklist(_claims())
    assert {
        "claim_id",
        "p_deny",
        "total_charge",
        "recoverability",
        "priority_score",
        "rank",
    } <= set(wl.columns)
    assert (wl["recoverability"] == 1.0).all()
    assert wl.columns[0] == "rank"


def test_worklist_uses_a_given_recoverability_column() -> None:
    claims = _claims().assign(recoverability=[1.0, 0.1, 1.0, 1.0])
    wl = build_worklist(claims).set_index("claim_id")
    assert wl.loc["SYN-CLM-2", "priority_score"] == pytest.approx(25.0)


def test_worklist_does_not_modify_its_input() -> None:
    claims = _claims()
    before = claims.copy()
    build_worklist(claims)
    pd.testing.assert_frame_equal(claims, before)
