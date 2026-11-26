"""FastAPI v1: /health, /score and /worklist.

uvicorn rcm.api.main:app --reload      # serves on :8000, reads $RCM_ARTIFACTS_DIR
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request, Response

from rcm.api.artifacts import Artifacts, load_artifacts, resolve_artifacts_dir
from rcm.api.schemas import (
    ClaimFeatures,
    HealthResponse,
    ScoreResponse,
    WorklistItem,
    WorklistResponse,
)
from rcm.models.features import FEATURES
from rcm.models.priority import DEFAULT_RECOVERABILITY, priority_score

MAX_PAGE = 1_000


def create_app(artifacts_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.artifacts = load_artifacts(resolve_artifacts_dir(artifacts_dir))
        yield

    app = FastAPI(
        title="AI Revenue Cycle Copilot API",
        version="1.0.0",
        description="Denial-risk scores and a priority worklist. Synthetic data only.",
        lifespan=lifespan,
    )

    def artifacts(request: Request) -> Artifacts:
        return request.app.state.artifacts

    def require_ready(request: Request) -> Artifacts:
        art = artifacts(request)
        if not art.ready:
            raise HTTPException(status_code=503, detail="Model or worklist not loaded")
        return art

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request, response: Response) -> HealthResponse:
        art = artifacts(request)
        if not art.ready:
            response.status_code = 503
        return HealthResponse(
            status="ok" if art.ready else "unavailable",
            model_loaded=art.model is not None,
            model=art.model_name if art.model is not None else None,
            worklist_rows=0 if art.worklist is None else len(art.worklist),
        )

    @app.post("/score", response_model=ScoreResponse)
    def score(claim: ClaimFeatures, request: Request) -> ScoreResponse:
        art = require_ready(request)
        row = pd.DataFrame([claim.model_dump(include=set(FEATURES))])[FEATURES]
        p = float(art.model.predict_proba(row)[0, 1])
        priority = float(priority_score([p], [claim.total_charge], DEFAULT_RECOVERABILITY)[0])
        return ScoreResponse(
            claim_id=claim.claim_id,
            p_deny=p,
            recoverability=DEFAULT_RECOVERABILITY,
            priority_score=priority,
            model=art.model_name,
        )

    @app.get("/worklist", response_model=WorklistResponse)
    def worklist(
        request: Request,
        limit: int = Query(50, ge=1, le=MAX_PAGE),
        offset: int = Query(0, ge=0),
    ) -> WorklistResponse:
        wl = require_ready(request).worklist
        page = wl.iloc[offset : offset + limit]
        return WorklistResponse(
            total=len(wl),
            limit=limit,
            offset=offset,
            items=[WorklistItem(**r) for r in page.to_dict(orient="records")],
        )

    return app


app = create_app()
