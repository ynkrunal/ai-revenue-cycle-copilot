"""Priority = P(deny) x balance x recoverability: the expected dollars at stake.

Until Step 11 adds the CARC-group lookup, recoverability defaults to 1.0 for every claim,
so the ranking is P(deny) x billed charge.
"""

import numpy as np
import pandas as pd

DEFAULT_RECOVERABILITY = 1.0


def priority_score(
    p_deny: np.ndarray, balance: np.ndarray, recoverability: np.ndarray | float = 1.0
) -> np.ndarray:
    p = np.asarray(p_deny, dtype=float)
    b = np.asarray(balance, dtype=float)
    r = np.broadcast_to(np.asarray(recoverability, dtype=float), p.shape)
    if not (np.isfinite(p).all() and np.isfinite(b).all() and np.isfinite(r).all()):
        raise ValueError("priority inputs must be finite numbers")
    if ((p < 0) | (p > 1)).any():
        raise ValueError("p_deny must be between 0 and 1")
    if (b < 0).any():
        raise ValueError("balance cannot be negative")
    if ((r < 0) | (r > 1)).any():
        raise ValueError("recoverability must be between 0 and 1")
    return p * b * r


def build_worklist(
    claims: pd.DataFrame,
    p_col: str = "p_deny",
    balance_col: str = "total_charge",
    recoverability_col: str = "recoverability",
) -> pd.DataFrame:
    """Rank claims by priority, highest first. Ties break by claim_id so order is stable."""
    wl = claims.copy()
    if recoverability_col not in wl:
        wl[recoverability_col] = DEFAULT_RECOVERABILITY
    wl["priority_score"] = priority_score(wl[p_col], wl[balance_col], wl[recoverability_col])
    wl = wl.sort_values(
        ["priority_score", "claim_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    wl.insert(0, "rank", np.arange(1, len(wl) + 1))
    return wl
