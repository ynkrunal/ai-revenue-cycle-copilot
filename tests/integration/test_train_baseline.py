"""End to end: generate -> dbt build -> train baseline -> metrics + worklist CSV."""

import json
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate
from rcm.generator.io import write_tables
from rcm.models.features import FEATURES
from rcm.models.train import main
from tests.integration.dbt_helpers import query, run_dbt_build


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> dict:
    work = tmp_path_factory.mktemp("train")
    write_tables(
        generate(GeneratorConfig(seed=8, n_claims=30_000, months=18, start_date=date(2025, 1, 1))),
        work / "raw",
    )
    result = run_dbt_build(work / "raw", work)
    assert result.returncode == 0, result.stdout[-3000:]
    out = work / "artifacts"
    assert main(["--db", str(work / "rcm.duckdb"), "--out", str(out)]) == 0
    return {"db": work / "rcm.duckdb", "out": out}


def test_artifacts_are_written(run: dict) -> None:
    for name in ("baseline_logreg.joblib", "metrics.json", "worklist.csv"):
        assert (run["out"] / name).is_file(), name


def test_metrics_are_logged_and_beat_chance(run: dict) -> None:
    m = json.loads((run["out"] / "metrics.json").read_text())
    hold = m["holdout"]
    assert hold["pr_auc"] > 1.5 * hold["base_rate"]
    assert hold["roc_auc"] > 0.6
    assert hold["precision_at_k"] > hold["base_rate"]
    assert m["model"] == "baseline_logreg"
    assert m["features"] == FEATURES


def test_split_uses_the_agreed_months_and_drops_the_tail(run: dict) -> None:
    m = json.loads((run["out"] / "metrics.json").read_text())
    split = m["split"]
    assert split["holdout_months"] == ["2026-04", "2026-05", "2026-06"]
    assert split["train_months"][-1] == "2026-03"
    assert all(month >= "2026-07" for month in split["tail_months"])
    ((total,),) = query(run["db"], "select count(*) from main_marts.feat_claims_at_submission")
    assert split["n_train"] + split["n_holdout"] + split["n_tail"] == total
    assert split["n_tail"] > 0


def test_tail_is_reported_apart_and_not_scored(run: dict) -> None:
    m = json.loads((run["out"] / "metrics.json").read_text())
    tail = m["excluded_tail"]
    assert tail["n"] == m["split"]["n_tail"]
    assert "reason" in tail
    assert "pr_auc" not in tail and "roc_auc" not in tail


def test_worklist_is_the_holdout_sorted_by_priority(run: dict) -> None:
    wl = pd.read_csv(run["out"] / "worklist.csv")
    m = json.loads((run["out"] / "metrics.json").read_text())
    assert len(wl) == m["split"]["n_holdout"]
    assert wl["priority_score"].is_monotonic_decreasing
    assert list(wl["rank"]) == list(range(1, len(wl) + 1))
    assert wl["claim_id"].is_unique
    months = pd.to_datetime(wl["submission_date"]).dt.strftime("%Y-%m")
    assert set(months) <= {"2026-04", "2026-05", "2026-06"}
    expected = wl["p_deny"] * wl["total_charge"] * wl["recoverability"]
    assert (wl["priority_score"] - expected).abs().max() < 0.01


def test_worklist_carries_no_outcome_columns(run: dict) -> None:
    wl = pd.read_csv(run["out"] / "worklist.csv", nrows=1)
    assert not set(wl.columns) & {"is_denied", "claim_status", "denied_amount", "paid_amount",
                                  "primary_denial_carc"}  # fmt: skip


def test_priority_captures_more_denied_dollars_than_sorting_by_charge(run: dict) -> None:
    m = json.loads((run["out"] / "metrics.json").read_text())
    w = m["worklist"]
    assert (
        w["denied_dollars_captured_at_k"]["priority"]
        > w["denied_dollars_captured_at_k"]["total_charge"]
    )


def test_saved_model_reloads_and_scores(run: dict) -> None:
    model = joblib.load(run["out"] / "baseline_logreg.joblib")
    rows = query(run["db"], "select * from main_marts.feat_claims_at_submission limit 5")
    cols = [r[0] for r in query(run["db"], "describe main_marts.feat_claims_at_submission")]
    frame = pd.DataFrame(rows, columns=cols)
    p = model.predict_proba(frame[FEATURES])[:, 1]
    assert ((p >= 0) & (p <= 1)).all()


def test_cli_default_paths_come_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from rcm.models.train import resolve_paths

    monkeypatch.delenv("RCM_DUCKDB_PATH", raising=False)
    monkeypatch.delenv("RCM_ARTIFACTS_DIR", raising=False)
    assert resolve_paths(None, None) == (Path("data/rcm.duckdb"), Path("models/artifacts"))
    monkeypatch.setenv("RCM_DUCKDB_PATH", str(tmp_path / "x.duckdb"))
    monkeypatch.setenv("RCM_ARTIFACTS_DIR", str(tmp_path / "art"))
    assert resolve_paths(None, None) == (tmp_path / "x.duckdb", tmp_path / "art")
