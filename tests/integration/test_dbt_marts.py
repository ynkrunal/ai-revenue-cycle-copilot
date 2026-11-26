"""Build the full dbt project on a sample and check the marts against the raw data."""

import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from rcm.generator import GeneratorConfig, generate, reference
from rcm.generator.io import read_tables, write_tables
from rcm.generator.schema import SCHEMAS
from tests.integration.dbt_helpers import DBT_PROJECT, query, run_dbt_build

REMIT_COLUMNS = (set(SCHEMAS["remits"]) | set(SCHEMAS["remit_adjustments"])) - {
    "claim_id",
    "claim_line_id",
}
LABEL_COLUMNS = {
    "is_denied",
    "claim_status",
    "primary_denial_carc",
    "denial_carc_group",
    "denied_amount",
}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict:
    work = tmp_path_factory.mktemp("marts")
    raw = work / "raw"
    write_tables(
        generate(GeneratorConfig(seed=4, n_claims=6_000, months=6, start_date=date(2025, 1, 1))),
        raw,
    )
    result = run_dbt_build(raw, work)
    assert result.returncode == 0, result.stdout[-4000:]
    return {"raw": read_tables(raw), "db": work / "rcm.duckdb", "work": work}


def _df(db: Path, sql: str, columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(query(db, sql), columns=columns)


def _columns(db: Path, model: str) -> list[str]:
    rows = query(
        db,
        "select column_name from information_schema.columns "
        f"where table_schema = 'main_marts' and table_name = '{model}' "
        "order by ordinal_position",
    )
    return [r[0] for r in rows]


# --- leakage ----------------------------------------------------------------------------------


def test_features_have_no_remit_or_label_columns(built: dict) -> None:
    cols = set(_columns(built["db"], "feat_claims_at_submission"))
    assert cols, "feature table missing"
    assert not cols & REMIT_COLUMNS
    assert not cols & LABEL_COLUMNS


def test_feature_lineage_never_touches_remits(built: dict) -> None:
    """Follow dbt's own dependency graph from the feature model all the way to sources."""
    manifest = json.loads((built["work"] / "target" / "manifest.json").read_text())
    nodes = {**manifest["nodes"], **manifest["sources"]}
    start = "model.rcm.feat_claims_at_submission"
    seen, todo = set(), [start]
    while todo:
        for dep in nodes[todo.pop()].get("depends_on", {}).get("nodes", []):
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    assert "source.rcm.raw.claims" in seen
    assert not {d for d in seen if "remit" in d or "outcome" in d or "fct_claims" in d}


def test_leakage_test_fails_when_a_remit_column_is_added(tmp_path: Path, built: dict) -> None:
    project = tmp_path / "dbt"
    shutil.copytree(DBT_PROJECT, project, ignore=shutil.ignore_patterns("target", "logs"))
    feat = project / "models" / "marts" / "feat_claims_at_submission.sql"
    sql = feat.read_text()
    feat.write_text(sql.replace("from features", ", 0.0 as paid_amount\nfrom features", 1))
    raw = tmp_path / "raw"
    write_tables(generate(GeneratorConfig(seed=5, n_claims=300, months=2)), raw)
    result = run_dbt_build(raw, tmp_path, project_dir=project)
    assert result.returncode != 0
    assert "assert_no_remit_columns_in_features" in result.stdout
    assert "FAIL" in result.stdout


# --- fct_claims ---------------------------------------------------------------------------------


def test_fct_claims_has_one_row_per_claim_and_correct_label(built: dict) -> None:
    raw = built["raw"]
    fct = _df(
        built["db"],
        "select claim_id, is_denied, claim_status from main_marts.fct_claims",
        ["claim_id", "is_denied", "claim_status"],
    ).set_index("claim_id")
    assert len(fct) == len(raw["claims"])
    status = raw["remits"].set_index("claim_id")["claim_status"]
    assert (fct["claim_status"] == status.reindex(fct.index)).all()
    assert (fct["is_denied"] == (status.reindex(fct.index) != "paid")).all()


def test_fct_claims_denial_reason_and_amounts(built: dict) -> None:
    raw = built["raw"]
    fct = _df(
        built["db"],
        "select claim_id, primary_denial_carc, denied_amount, paid_amount, total_charge "
        "from main_marts.fct_claims",
        ["claim_id", "carc", "denied", "paid", "charge"],
    ).set_index("claim_id")
    adj = raw["remit_adjustments"].merge(raw["remits"][["remit_id", "claim_id"]], on="remit_id")
    denial = adj[adj["carc_code"].isin(reference.DENIAL_CARC)]
    expected_amount = denial.groupby("claim_id")["adjustment_amount"].sum()
    got = fct["denied"].astype(float)
    assert got.reindex(expected_amount.index).round(2).equals(expected_amount.round(2))
    assert (got.drop(expected_amount.index) == 0).all()
    expected_carc = denial.drop_duplicates("claim_id").set_index("claim_id")["carc_code"]
    assert (fct["carc"].reindex(expected_carc.index) == expected_carc).all()
    assert fct["carc"].drop(expected_carc.index).isna().all()


# --- features -----------------------------------------------------------------------------------


def test_features_one_row_per_claim_with_correct_values(built: dict) -> None:
    raw = built["raw"]
    feat = _df(
        built["db"],
        "select claim_id, days_to_submit, missing_prior_auth, past_timely_filing_limit, "
        "patient_age_at_service, primary_cpt_code, submission_month "
        "from main_marts.feat_claims_at_submission",
        ["claim_id", "lag", "missing_auth", "late", "age", "cpt", "month"],
    ).set_index("claim_id")
    claims = raw["claims"].set_index("claim_id")
    assert set(feat.index) == set(claims.index)
    feat = feat.reindex(claims.index)

    lag = (claims["submission_date"] - claims["service_date"]).dt.days
    assert (feat["lag"] == lag).all()
    assert (
        feat["missing_auth"] == (claims["requires_prior_auth"] & ~claims["prior_auth_obtained"])
    ).all()
    limit = claims["payer_id"].map(raw["payers"].set_index("payer_id")["timely_filing_days"])
    assert (feat["late"] == (lag > limit)).all()
    birth = claims["patient_id"].map(raw["patients"].set_index("patient_id")["birth_year"])
    assert (feat["age"] == claims["service_date"].dt.year - birth).all()
    first = raw["claim_lines"].query("line_number == 1").set_index("claim_id")["cpt_code"]
    assert (feat["cpt"] == first.reindex(claims.index)).all()
    month = claims["submission_date"].dt.to_period("M").dt.to_timestamp()
    assert (pd.to_datetime(feat["month"]) == month).all()


# --- KPIs ---------------------------------------------------------------------------------------


def test_kpis_reconcile_with_raw_data(built: dict) -> None:
    raw = built["raw"]
    kpi = _df(
        built["db"],
        "select submission_month, sum(claims), sum(denied_claims) "
        "from main_marts.mart_denial_kpis group by 1",
        ["month", "claims", "denied"],
    )
    kpi["month"] = pd.to_datetime(kpi["month"])
    claims = raw["claims"].merge(raw["remits"][["claim_id", "claim_status"]], on="claim_id")
    claims["month"] = claims["submission_date"].dt.to_period("M").dt.to_timestamp()
    expected = claims.groupby("month").agg(
        claims=("claim_id", "size"), denied=("claim_status", lambda s: (s != "paid").sum())
    )
    got = kpi.set_index("month").sort_index()
    assert (got["claims"] == expected["claims"]).all()
    assert (got["denied"] == expected["denied"]).all()


def test_kpi_denial_rate_and_top_reason(built: dict) -> None:
    rows = _df(
        built["db"],
        "select denial_rate, denied_claims, claims, top_denial_carc "
        "from main_marts.mart_denial_kpis",
        ["rate", "denied", "claims", "top"],
    )
    assert ((rows["rate"] >= 0) & (rows["rate"] <= 1)).all()
    assert (rows["rate"] - rows["denied"] / rows["claims"]).abs().max() < 1e-9
    assert rows.loc[rows["denied"] > 0, "top"].notna().all()
    assert rows.loc[rows["denied"] == 0, "top"].isna().all()


def test_dims_cover_every_payer_and_provider(built: dict) -> None:
    raw = built["raw"]
    ((payers,),) = query(built["db"], "select count(*) from main_marts.dim_payer")
    ((providers,),) = query(built["db"], "select count(*) from main_marts.dim_provider")
    assert payers == len(raw["payers"])
    assert providers == len(raw["providers"])
