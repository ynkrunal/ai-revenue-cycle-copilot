"""Evaluation metrics, checked on tiny hand-worked examples."""

import numpy as np
import pytest

from rcm.models.metrics import dollars_captured_at_k, evaluate, precision_at_k


def test_precision_at_k() -> None:
    y = np.array([1, 0, 1, 0, 0])
    scores = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
    assert precision_at_k(y, scores, 1) == 1.0
    assert precision_at_k(y, scores, 2) == 0.5
    assert precision_at_k(y, scores, 3) == pytest.approx(2 / 3)


def test_precision_at_k_caps_k_at_length() -> None:
    assert precision_at_k(np.array([1, 0]), np.array([0.5, 0.4]), 10) == 0.5


def test_dollars_captured_at_k() -> None:
    order_by = np.array([3.0, 2.0, 1.0])
    denied = np.array([0.0, 50.0, 150.0])
    assert dollars_captured_at_k(order_by, denied, 2) == pytest.approx(50 / 200)
    assert dollars_captured_at_k(order_by, denied, 3) == pytest.approx(1.0)


def test_dollars_captured_is_zero_when_nothing_was_denied() -> None:
    assert dollars_captured_at_k(np.array([1.0, 2.0]), np.zeros(2), 1) == 0.0


def test_evaluate_reports_all_metrics() -> None:
    rng = np.random.default_rng(0)
    y = rng.random(2_000) < 0.1
    p = np.clip(0.1 + 0.5 * y + rng.normal(0, 0.15, 2_000), 0, 1)
    m = evaluate(y.astype(int), p, k=100)
    assert set(m) >= {"pr_auc", "roc_auc", "brier", "base_rate", "precision_at_k", "k", "n"}
    assert m["n"] == 2_000 and m["k"] == 100
    assert m["base_rate"] == pytest.approx(y.mean())
    assert m["pr_auc"] > m["base_rate"]
    assert 0.5 < m["roc_auc"] <= 1.0
    assert 0.0 <= m["brier"] <= 1.0


def test_evaluate_needs_both_classes() -> None:
    with pytest.raises(ValueError):
        evaluate(np.zeros(10, dtype=int), np.full(10, 0.1), k=5)
