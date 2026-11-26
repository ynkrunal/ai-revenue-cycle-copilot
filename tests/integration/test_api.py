"""FastAPI v1 through TestClient, on artifacts from the real Step 6 pipeline."""

from datetime import date
from pathlib import Path

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from rcm.api.main import create_app
from rcm.generator import GeneratorConfig, generate
from rcm.generator.io import write_tables
from rcm.models.features import FEATURES
from rcm.models.train import main as train_main
from tests.integration.dbt_helpers import query, run_dbt_build


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory: pytest.TempPathFactory) -> dict:
    work = tmp_path_factory.mktemp("api")
    write_tables(
        generate(GeneratorConfig(seed=21, n_claims=20_000, months=18, start_date=date(2025, 1, 1))),
        work / "raw",
    )
    result = run_dbt_build(work / "raw", work)
    assert result.returncode == 0, result.stdout[-3000:]
    artifacts = work / "artifacts"
    assert train_main(["--db", str(work / "rcm.duckdb"), "--out", str(artifacts)]) == 0
    cols = [
        r[0] for r in query(work / "rcm.duckdb", "describe main_marts.feat_claims_at_submission")
    ]
    rows = query(work / "rcm.duckdb", "select * from main_marts.feat_claims_at_submission")
    return {"artifacts": artifacts, "features": pd.DataFrame(rows, columns=cols)}


@pytest.fixture(scope="module")
def client(pipeline: dict):
    with TestClient(create_app(pipeline["artifacts"])) as c:
        yield c


@pytest.fixture
def empty_client(tmp_path: Path):
    with TestClient(create_app(tmp_path / "nothing-here")) as c:
        yield c


def _payload(row: pd.Series) -> dict:
    body = {"claim_id": row["claim_id"]}
    for f in FEATURES:
        value = row[f]
        body[f] = value.item() if hasattr(value, "item") else value
        if f in ("total_charge", "max_line_charge"):
            body[f] = float(value)
    return body


# --- /health ------------------------------------------------------------------------------------


def test_health_reports_ready(client: TestClient, pipeline: dict) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    rows = len(pd.read_csv(pipeline["artifacts"] / "worklist.csv"))
    assert body == {"status": "ok", "model_loaded": True, "model": "baseline_logreg",
                    "worklist_rows": rows}  # fmt: skip


def test_health_without_artifacts_is_503(empty_client: TestClient) -> None:
    r = empty_client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "unavailable"
    assert r.json()["model_loaded"] is False


# --- /score -------------------------------------------------------------------------------------


def test_score_matches_the_saved_model(client: TestClient, pipeline: dict) -> None:
    row = pipeline["features"].iloc[123]
    r = client.post("/score", json=_payload(row))
    assert r.status_code == 200, r.text
    body = r.json()
    model = joblib.load(pipeline["artifacts"] / "baseline_logreg.joblib")
    expected = model.predict_proba(pipeline["features"].iloc[[123]][FEATURES])[0, 1]
    assert body["claim_id"] == row["claim_id"]
    assert body["p_deny"] == pytest.approx(expected, abs=1e-9)
    assert body["recoverability"] == 1.0
    assert body["priority_score"] == pytest.approx(expected * float(row["total_charge"]), abs=1e-6)
    assert body["model"] == "baseline_logreg"


def test_score_agrees_with_the_worklist(client: TestClient, pipeline: dict) -> None:
    wl = pd.read_csv(pipeline["artifacts"] / "worklist.csv", dtype={"claim_id": str})
    top = wl.iloc[0]
    row = pipeline["features"].set_index("claim_id").loc[top["claim_id"]].copy()
    row["claim_id"] = top["claim_id"]
    body = client.post("/score", json=_payload(row)).json()
    assert body["p_deny"] == pytest.approx(top["p_deny"], abs=1e-7)


def test_score_accepts_an_unseen_cpt_code(client: TestClient, pipeline: dict) -> None:
    body = _payload(pipeline["features"].iloc[0]) | {"primary_cpt_code": "00000"}
    r = client.post("/score", json=body)
    assert r.status_code == 200
    assert 0.0 <= r.json()["p_deny"] <= 1.0


@pytest.mark.parametrize(
    "change",
    [{"total_charge": -5.0}, {"payer_type": "unknown"}, {"paid_amount": 10.0},
     {"is_denied": True}],
)  # fmt: skip
def test_score_rejects_bad_or_leaky_input(client: TestClient, pipeline: dict, change: dict) -> None:
    r = client.post("/score", json=_payload(pipeline["features"].iloc[0]) | change)
    assert r.status_code == 422


def test_score_rejects_a_missing_feature(client: TestClient, pipeline: dict) -> None:
    body = _payload(pipeline["features"].iloc[0])
    del body["missing_prior_auth"]
    r = client.post("/score", json=body)
    assert r.status_code == 422
    assert "missing_prior_auth" in r.text


def test_score_without_a_model_is_503(empty_client: TestClient, pipeline: dict) -> None:
    r = empty_client.post("/score", json=_payload(pipeline["features"].iloc[0]))
    assert r.status_code == 503


# --- /worklist ----------------------------------------------------------------------------------


def test_worklist_default_page(client: TestClient, pipeline: dict) -> None:
    r = client.get("/worklist")
    assert r.status_code == 200
    body = r.json()
    total = len(pd.read_csv(pipeline["artifacts"] / "worklist.csv"))
    assert body["total"] == total
    assert body["limit"] == 50 and body["offset"] == 0
    items = body["items"]
    assert [i["rank"] for i in items] == list(range(1, 51))
    scores = [i["priority_score"] for i in items]
    assert scores == sorted(scores, reverse=True)


def test_worklist_limit_and_offset(client: TestClient) -> None:
    page = client.get("/worklist", params={"limit": 5, "offset": 5}).json()
    assert [i["rank"] for i in page["items"]] == [6, 7, 8, 9, 10]


def test_worklist_keeps_codes_as_text(client: TestClient) -> None:
    item = client.get("/worklist", params={"limit": 1}).json()["items"][0]
    assert isinstance(item["primary_cpt_code"], str) and len(item["primary_cpt_code"]) == 5
    assert item["claim_id"].startswith("SYN-CLM-")


def test_worklist_past_the_end_is_empty(client: TestClient) -> None:
    body = client.get("/worklist", params={"limit": 10, "offset": 10_000_000}).json()
    assert body["items"] == []


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"offset": -1}])
def test_worklist_rejects_bad_paging(client: TestClient, params: dict) -> None:
    assert client.get("/worklist", params=params).status_code == 422


def test_worklist_without_artifacts_is_503(empty_client: TestClient) -> None:
    assert empty_client.get("/worklist").status_code == 503


def test_worklist_has_no_outcome_fields(client: TestClient) -> None:
    item = client.get("/worklist", params={"limit": 1}).json()["items"][0]
    assert not set(item) & {"is_denied", "claim_status", "denied_amount", "paid_amount"}


# --- app wiring ---------------------------------------------------------------------------------


def test_openapi_lists_the_three_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/score", "/worklist"} <= set(paths)


def test_artifacts_dir_defaults_to_env_var(monkeypatch: pytest.MonkeyPatch, pipeline: dict) -> None:
    monkeypatch.setenv("RCM_ARTIFACTS_DIR", str(pipeline["artifacts"]))
    with TestClient(create_app()) as c:
        assert c.get("/health").json()["model_loaded"] is True


def test_module_level_app_exists_for_uvicorn() -> None:
    from rcm.api.main import app

    assert app.title
