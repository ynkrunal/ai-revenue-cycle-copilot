"""Time-based split by submission month. Never a random split.

With the default 18-month window starting January 2025:
  train   = submission months before April 2026
  holdout = April, May and June 2026 (the last 3 months of the window)
  tail    = July 2026 onward, dropped: these months only hold claims for visits before
            July 2026 (end-of-June visits plus slow filers), so they are incomplete and
            skewed toward late claims. Kept out of training and every metric.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

WINDOW_START = date(2025, 1, 1)
WINDOW_MONTHS = 18
HOLDOUT_MONTHS = 3
MONTH_COLUMN = "submission_month"


@dataclass(frozen=True)
class Split:
    train: pd.DataFrame
    holdout: pd.DataFrame
    tail: pd.DataFrame

    def describe(self) -> dict:
        def months(df: pd.DataFrame) -> list[str]:
            return sorted(pd.to_datetime(df[MONTH_COLUMN]).dt.strftime("%Y-%m").unique())

        return {
            "train_months": months(self.train),
            "holdout_months": months(self.holdout),
            "tail_months": months(self.tail),
            "n_train": len(self.train),
            "n_holdout": len(self.holdout),
            "n_tail": len(self.tail),
        }


def time_split(
    frame: pd.DataFrame,
    window_start: date = WINDOW_START,
    window_months: int = WINDOW_MONTHS,
    holdout_months: int = HOLDOUT_MONTHS,
) -> Split:
    if not 0 < holdout_months < window_months:
        raise ValueError("holdout_months must be at least 1 and shorter than the window")

    window_end = pd.Timestamp(window_start) + pd.DateOffset(months=window_months)
    holdout_start = window_end - pd.DateOffset(months=holdout_months)
    month = pd.to_datetime(frame[MONTH_COLUMN])

    split = Split(
        train=frame[month < holdout_start].copy(),
        holdout=frame[(month >= holdout_start) & (month < window_end)].copy(),
        tail=frame[month >= window_end].copy(),
    )
    if split.holdout.empty:
        raise ValueError(f"holdout is empty: no claims submitted from {holdout_start:%Y-%m}")
    if split.train.empty:
        raise ValueError("training set is empty")
    return split
