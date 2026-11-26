"""Train the baseline, evaluate on the time holdout, write metrics and the worklist.

python -m rcm.models.train [--db data/rcm.duckdb] [--out models/artifacts]
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import sklearn

from rcm.models.baseline import build_baseline
from rcm.models.features import FEATURES, LABEL, load_training_frame
from rcm.models.metrics import dollars_captured_at_k, evaluate
from rcm.models.priority import build_worklist
from rcm.models.split import HOLDOUT_MONTHS, WINDOW_MONTHS, WINDOW_START, time_split

MODEL_NAME = "baseline_logreg"
DEFAULT_TOP_K = 500
TAIL_REASON = (
    "Submitted after the 18-month service window ends. These months only hold claims for "
    "visits before the window closed, so they are incomplete and skewed toward slow filers "
    "(about 45% sent 30+ days late vs about 5% in a normal month). Excluded from training "
    "and from every holdout metric."
)
WORKLIST_COLUMNS = [
    "claim_id",
    "submission_date",
    "payer_id",
    "payer_type",
    "provider_id",
    "provider_specialty",
    "primary_cpt_code",
    "total_charge",
]


def resolve_paths(db: str | None, out: str | None) -> tuple[Path, Path]:
    """Flag first, then environment variable, then the default."""
    return (
        Path(db or os.environ.get("RCM_DUCKDB_PATH") or "data/rcm.duckdb"),
        Path(out or os.environ.get("RCM_ARTIFACTS_DIR") or "models/artifacts"),
    )


def run_training(
    db_path: Path,
    out_dir: Path,
    window_start: date = WINDOW_START,
    window_months: int = WINDOW_MONTHS,
    holdout_months: int = HOLDOUT_MONTHS,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    frame = load_training_frame(db_path)
    split = time_split(frame, window_start, window_months, holdout_months)
    train, holdout, tail = split.train, split.holdout, split.tail

    model = build_baseline().fit(train[FEATURES], train[LABEL])
    p_train = model.predict_proba(train[FEATURES])[:, 1]
    p_hold = model.predict_proba(holdout[FEATURES])[:, 1]

    worklist = build_worklist(holdout[WORKLIST_COLUMNS].assign(p_deny=p_hold))
    worklist["p_deny"] = worklist["p_deny"].round(8)
    worklist["priority_score"] = worklist["priority_score"].round(4)

    denied = holdout["denied_amount"].to_numpy()
    charge = holdout["total_charge"].to_numpy()
    metrics = {
        "model": MODEL_NAME,
        "sklearn_version": sklearn.__version__,
        "features": FEATURES,
        "split": split.describe(),
        "train": evaluate(train[LABEL], p_train, top_k),
        "holdout": evaluate(holdout[LABEL], p_hold, top_k),
        "excluded_tail": {
            "n": len(tail),
            "months": split.describe()["tail_months"],
            "actual_denial_rate": float(tail[LABEL].mean()) if len(tail) else None,
            "reason": TAIL_REASON,
        },
        "worklist": {
            "rows": len(worklist),
            "k": top_k,
            "recoverability": "1.0 for all claims until Step 11",
            "denied_dollars_captured_at_k": {
                "priority": dollars_captured_at_k(p_hold * charge, denied, top_k),
                "p_deny": dollars_captured_at_k(p_hold, denied, top_k),
                "total_charge": dollars_captured_at_k(charge, denied, top_k),
                "random_expected": top_k / len(holdout),
            },
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / f"{MODEL_NAME}.joblib")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    worklist.to_csv(out_dir / "worklist.csv", index=False)
    return metrics


def _summary(m: dict) -> str:
    h, t, s = m["holdout"], m["train"], m["split"]
    cap = m["worklist"]["denied_dollars_captured_at_k"]
    lines = [
        f"Split: train {s['train_months'][0]}..{s['train_months'][-1]} (n={s['n_train']:,}), "
        f"holdout {s['holdout_months'][0]}..{s['holdout_months'][-1]} (n={s['n_holdout']:,}), "
        f"tail dropped (n={s['n_tail']:,})",
        f"{'':<9}{'PR-AUC':>8}{'ROC-AUC':>9}{'Brier':>8}{'base':>7}{'P@k':>7}",
    ]
    for name, r in (("train", t), ("holdout", h)):
        lines.append(
            f"{name:<9}{r['pr_auc']:>8.3f}{r['roc_auc']:>9.3f}{r['brier']:>8.4f}"
            f"{r['base_rate']:>7.3f}{r['precision_at_k']:>7.3f}"
        )
    lines.append(
        f"Denied $ captured in top {m['worklist']['k']}: priority {cap['priority']:.1%}, "
        f"p_deny {cap['p_deny']:.1%}, charge {cap['total_charge']:.1%}, "
        f"random {cap['random_expected']:.1%}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rcm.models.train", description=__doc__)
    parser.add_argument("--db", default=None, help="DuckDB file (default: $RCM_DUCKDB_PATH)")
    parser.add_argument("--out", default=None, help="artifacts folder ($RCM_ARTIFACTS_DIR)")
    parser.add_argument("--window-start", type=date.fromisoformat, default=WINDOW_START)
    parser.add_argument("--window-months", type=int, default=WINDOW_MONTHS)
    parser.add_argument("--holdout-months", type=int, default=HOLDOUT_MONTHS)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args(argv)

    db_path, out_dir = resolve_paths(args.db, args.out)
    np.random.seed(0)
    metrics = run_training(
        db_path, out_dir, args.window_start, args.window_months, args.holdout_months, args.top_k
    )
    print(_summary(metrics))
    print(f"Wrote model, metrics.json and worklist.csv to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
