"""Time-based split: train before April 2026, holdout April-June 2026, late tail dropped."""

from datetime import date

import pandas as pd
import pytest

from rcm.models.split import time_split


def _frame(months: pd.DatetimeIndex, per_month: int = 3) -> pd.DataFrame:
    rows = [
        {"claim_id": f"SYN-CLM-{i:07d}", "submission_month": m}
        for i, m in enumerate(m for m in months for _ in range(per_month))
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def frame() -> pd.DataFrame:
    return _frame(pd.date_range("2025-01-01", "2026-10-01", freq="MS"))


def test_default_split_matches_the_agreed_months(frame: pd.DataFrame) -> None:
    split = time_split(frame)
    assert split.train["submission_month"].max() == pd.Timestamp("2026-03-01")
    assert split.train["submission_month"].min() == pd.Timestamp("2025-01-01")
    assert sorted(split.holdout["submission_month"].unique()) == list(
        pd.to_datetime(["2026-04-01", "2026-05-01", "2026-06-01"])
    )
    assert sorted(split.tail["submission_month"].unique()) == list(
        pd.to_datetime(["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"])
    )


def test_split_is_a_clean_partition(frame: pd.DataFrame) -> None:
    split = time_split(frame)
    ids = [set(part["claim_id"]) for part in (split.train, split.holdout, split.tail)]
    assert not ids[0] & ids[1] and not ids[0] & ids[2] and not ids[1] & ids[2]
    assert set().union(*ids) == set(frame["claim_id"])


def test_every_training_month_is_before_every_holdout_month(frame: pd.DataFrame) -> None:
    split = time_split(frame)
    assert split.train["submission_month"].max() < split.holdout["submission_month"].min()


def test_split_follows_a_different_window() -> None:
    frame = _frame(pd.date_range("2025-03-01", "2025-12-01", freq="MS"))
    split = time_split(frame, window_start=date(2025, 3, 1), window_months=8, holdout_months=2)
    assert sorted(split.holdout["submission_month"].dt.month.unique()) == [9, 10]
    assert sorted(split.tail["submission_month"].dt.month.unique()) == [11, 12]
    assert split.train["submission_month"].max() == pd.Timestamp("2025-08-01")


def test_split_describes_itself(frame: pd.DataFrame) -> None:
    info = time_split(frame).describe()
    assert info["holdout_months"] == ["2026-04", "2026-05", "2026-06"]
    assert info["train_months"][0] == "2025-01" and info["train_months"][-1] == "2026-03"
    assert info["tail_months"] == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert info["n_train"] + info["n_holdout"] + info["n_tail"] == len(frame)


def test_empty_holdout_is_an_error() -> None:
    frame = _frame(pd.date_range("2025-01-01", "2025-06-01", freq="MS"))
    with pytest.raises(ValueError, match="holdout"):
        time_split(frame)


def test_invalid_holdout_length_is_an_error(frame: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        time_split(frame, holdout_months=0)
    with pytest.raises(ValueError):
        time_split(frame, window_months=3, holdout_months=3)
