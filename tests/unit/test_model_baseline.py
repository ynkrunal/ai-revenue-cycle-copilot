"""The baseline logistic regression pipeline on a small hand-built feature frame."""

import numpy as np
import pandas as pd

from rcm.models.baseline import build_baseline
from rcm.models.features import BOOLEAN, CATEGORICAL, FEATURES, NUMERIC
from rcm.models.metrics import evaluate


def _frame(n: int, seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {c: rng.choice(["a", "b", "c"], size=n) for c in CATEGORICAL}
        | {c: rng.lognormal(3, 1, size=n) for c in NUMERIC}
        | {c: rng.random(n) < 0.2 for c in BOOLEAN}
    )
    logit = -2.5 + 2.5 * df["missing_prior_auth"] + 1.0 * (df["payer_type"] == "a")
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df[FEATURES], y.to_numpy()


def test_pipeline_learns_a_planted_signal() -> None:
    x, y = _frame(4_000, seed=1)
    model = build_baseline().fit(x, y)
    x_test, y_test = _frame(2_000, seed=2)
    p = model.predict_proba(x_test)[:, 1]
    m = evaluate(y_test, p, k=200)
    assert m["roc_auc"] > 0.7
    assert m["pr_auc"] > 1.5 * m["base_rate"]


def test_probabilities_are_valid_and_unseen_categories_are_ok() -> None:
    x, y = _frame(1_000, seed=3)
    model = build_baseline().fit(x, y)
    x_new = x.head(5).copy()
    x_new["payer_type"] = "never_seen_before"
    p = model.predict_proba(x_new)[:, 1]
    assert ((p >= 0) & (p <= 1)).all()


def test_pipeline_is_deterministic() -> None:
    x, y = _frame(1_000, seed=4)
    p1 = build_baseline().fit(x, y).predict_proba(x)[:, 1]
    p2 = build_baseline().fit(x, y).predict_proba(x)[:, 1]
    assert np.array_equal(p1, p2)


def test_pipeline_ignores_columns_that_are_not_declared_features() -> None:
    x, y = _frame(500, seed=5)
    model = build_baseline().fit(x.assign(paid_amount=1.0), y)
    used = model.named_steps["prep"].get_feature_names_out()
    assert not [name for name in used if "paid_amount" in name]


def test_pipeline_accepts_decimal_money_from_raw_database_rows() -> None:
    from decimal import Decimal

    x, y = _frame(500, seed=6)
    model = build_baseline().fit(x, y)
    raw = x.head(3).copy()
    raw["total_charge"] = [Decimal("123.45"), Decimal("9.99"), Decimal("1500.00")]
    p = model.predict_proba(raw)[:, 1]
    assert ((p >= 0) & (p <= 1)).all()
