"""Evaluation metrics. PR-AUC is primary because denials are the rare class."""

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def _top_k(scores: np.ndarray, k: int) -> np.ndarray:
    order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
    return order[: min(k, len(order))]


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Share of the k highest-scored claims that were really denied."""
    return float(np.asarray(y_true)[_top_k(scores, k)].mean())


def dollars_captured_at_k(order_by: np.ndarray, denied_dollars: np.ndarray, k: int) -> float:
    """Share of all denied dollars that sit in the top k claims when sorted by `order_by`."""
    denied = np.asarray(denied_dollars, dtype=float)
    total = denied.sum()
    if total == 0:
        return 0.0
    return float(denied[_top_k(order_by, k)].sum() / total)


def evaluate(y_true: np.ndarray, p_deny: np.ndarray, k: int) -> dict:
    y = np.asarray(y_true).astype(int)
    if len(np.unique(y)) < 2:
        raise ValueError("evaluation needs both denied and paid claims")
    return {
        "n": int(len(y)),
        "base_rate": float(y.mean()),
        "pr_auc": float(average_precision_score(y, p_deny)),
        "roc_auc": float(roc_auc_score(y, p_deny)),
        "brier": float(brier_score_loss(y, p_deny)),
        "k": int(k),
        "precision_at_k": precision_at_k(y, p_deny, k),
    }
