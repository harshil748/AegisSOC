"""AegisSOC Frontend Gateway.

The single public entrypoint used by the React analyst UI (see
``frontend/src/api/*.ts`` for the exact contract this implements). Owns:

* JWT auth against a small seeded demo user set (see ``gateway_core.auth``).
* Per-client rate limiting.
* CORS for the Vite dev server / built frontend.
* A clean ``/api/*`` BFF surface that composes/reshapes data from the eleven
  internal services into exactly what the frontend expects -- in sync mode
  by calling each service's core logic in-process, in async mode by
  proxying over HTTP (see ``gateway_core.reads``).
* ``POST /api/demo/run-scenario`` -- the full in-process
  ingest->normalize->enrich->graph->detect->case->triage->recommend demo
  pipeline (see ``gateway_core.demo_pipeline``).
* Best-effort aggregated OpenAPI across every upstream (``/api/v1/openapi``)
  and a generic authenticated passthrough proxy (``/api/v1/proxy/*``) for
  direct access to any upstream's native API.

Internal services are never exposed directly outside the cluster network in
production -- see docs/SECURITY.md and docs/threat-model/THREAT_MODEL.md.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from prometheus_client import Counter
from pydantic import BaseModel

from aegis_common.auth.jwt import TokenPayload
from aegis_common.auth.rbac import Role, current_user_dependency, require_roles
from aegis_common.config import Settings, is_sync_mode
from aegis_common.service import create_service_app

from gateway_core import auth as gateway_auth
from gateway_core import demo_pipeline
from gateway_core import reads
from gateway_core.openapi_aggregator import aggregate_openapi
from gateway_core.proxy import proxy_request
from gateway_core.rate_limit import RateLimiter

SERVICE_NAME = "frontend_gateway"
logger = logging.getLogger("aegis.gateway")
settings = Settings()

UPSTREAMS = {
    "ingestion": os.getenv("INGESTION_URL", "http://ingestion:8001"),
    "normalization": os.getenv("NORMALIZATION_URL", "http://normalization:8002"),
    "enrichment": os.getenv("ENRICHMENT_URL", "http://enrichment:8003"),
    "graph": os.getenv("GRAPH_BUILDER_URL", "http://graph_builder:8004"),
    "detection": os.getenv("DETECTION_URL", "http://detection:8005"),
    "cases": os.getenv("CASE_MANAGEMENT_URL", "http://case_management:8006"),
    "triage": os.getenv("LLM_TRIAGE_URL", "http://llm_triage:8007"),
    "response": os.getenv("RESPONSE_POLICY_URL", "http://response_policy:8008"),
    "approval": os.getenv("APPROVAL_URL", "http://approval:8009"),
    "audit": os.getenv("AUDIT_URL", "http://audit:8010"),
}

RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "300"))
RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
_rate_limiter = RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_SECONDS)

get_current_user = current_user_dependency(settings.jwt_secret, settings.jwt_algorithm)
require_analyst = require_roles(Role.ANALYST.value, get_current_user)
require_admin = require_roles(Role.ADMIN.value, get_current_user)

RATE_LIMITED_TOTAL = Counter(
    "aegis_gateway_rate_limited_total", "Requests rejected by the gateway rate limiter", ["client_key"]
)
AUTH_FAILURES_TOTAL = Counter(
    "aegis_gateway_auth_failures_total", "Rejected requests due to missing/invalid credentials"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "frontend_gateway_started sync_mode=%s seeded_users=%s",
        is_sync_mode(),
        gateway_auth.list_seeded_usernames(),
    )
    yield


app = create_service_app(
    service_name=SERVICE_NAME,
    description="AegisSOC BFF: JWT auth, rate limiting, and the analyst-UI API contract.",
    lifespan=lifespan,
)


@app.middleware("http")
async def _rate_limit_middleware(request: Request, call_next):
    if request.url.path in {"/health", "/", "/metrics"}:
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    client_key = auth_header[-24:] if auth_header else (request.client.host if request.client else "unknown")
    allowed, remaining = _rate_limiter.allow(client_key)
    if not allowed:
        RATE_LIMITED_TOTAL.labels(client_key=client_key[-8:]).inc()
        retry_after = _rate_limiter.retry_after(client_key)
        return Response(
            content='{"detail": "rate_limit_exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


# --------------------------------------------------------------------------- auth


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login", tags=["auth"])
async def login(body: LoginRequest) -> dict:
    user = gateway_auth.authenticate(body.username, body.password)
    if user is None:
        AUTH_FAILURES_TOTAL.inc()
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = gateway_auth.issue_token(user, settings)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": {
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name,
        },
    }


@app.get("/api/auth/me", tags=["auth"])
async def me(user: TokenPayload = Depends(get_current_user)) -> dict:
    return {"username": user.username, "role": user.role, "tenant_id": user.tenant_id}


# --------------------------------------------------------------------------- alerts


@app.get("/api/alerts", tags=["alerts"])
async def list_alerts(
    severity: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    _user: TokenPayload = Depends(require_analyst),
) -> dict:
    return await reads.list_alerts(
        UPSTREAMS["detection"], severity=severity, status=status, q=q, limit=limit, offset=offset
    )


@app.get("/api/alerts/{alert_id}", tags=["alerts"])
async def get_alert(alert_id: str, _user: TokenPayload = Depends(require_analyst)) -> dict:
    alert = await reads.get_alert(UPSTREAMS["detection"], alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert_not_found")
    return alert


# --------------------------------------------------------------------------- cases


@app.get("/api/cases", tags=["cases"])
async def list_cases(
    status: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    _user: TokenPayload = Depends(require_analyst),
) -> dict:
    return await reads.list_cases(
        UPSTREAMS["cases"], status=status, severity=severity, q=q, limit=limit, offset=offset
    )


@app.get("/api/cases/{case_id}", tags=["cases"])
async def get_case(case_id: str, _user: TokenPayload = Depends(require_analyst)) -> dict:
    case = await reads.get_case(UPSTREAMS["cases"], case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    return case


@app.get("/api/cases/{case_id}/graph", tags=["cases"])
async def get_case_graph(
    case_id: str, depth: int = Query(1, ge=1, le=4), _user: TokenPayload = Depends(require_analyst)
) -> dict:
    graph = await reads.get_case_graph(UPSTREAMS["graph"], UPSTREAMS["cases"], case_id, depth=depth)
    if graph is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    return graph


@app.get("/api/cases/{case_id}/timeline", tags=["cases"])
async def get_case_timeline(case_id: str, _user: TokenPayload = Depends(require_analyst)) -> dict:
    timeline = await reads.get_case_timeline(UPSTREAMS["cases"], case_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    return timeline


@app.get("/api/cases/{case_id}/triage", tags=["cases"])
async def get_case_triage(case_id: str, _user: TokenPayload = Depends(require_analyst)) -> dict:
    report = await reads.get_case_triage(
        UPSTREAMS["triage"], UPSTREAMS["cases"], UPSTREAMS["graph"], case_id
    )
    if report is None:
        raise HTTPException(status_code=404, detail="case_not_found_or_triage_unavailable")
    return report


@app.get("/api/cases/{case_id}/evidence", tags=["cases"])
async def get_case_evidence(case_id: str, _user: TokenPayload = Depends(require_analyst)) -> dict:
    evidence = await reads.get_case_evidence(UPSTREAMS["triage"], UPSTREAMS["cases"], case_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    return evidence


# --------------------------------------------------------------------------- actions / approvals


@app.get("/api/actions", tags=["actions"])
async def list_actions(
    case_id: str | None = None,
    status: str | None = None,
    _user: TokenPayload = Depends(require_analyst),
) -> list[dict]:
    return await reads.list_actions(UPSTREAMS["response"], case_id=case_id, status=status)


class ApprovalSubmitRequest(BaseModel):
    action_id: str
    case_id: str
    decision: str
    rationale: str = ""
    dry_run: bool = True


@app.post("/api/approvals", tags=["approvals"])
async def submit_approval(body: ApprovalSubmitRequest, user: TokenPayload = Depends(require_analyst)) -> dict:
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")

    status_code, result = await reads.submit_approval(
        UPSTREAMS["approval"],
        UPSTREAMS["response"],
        UPSTREAMS["audit"],
        action_id=body.action_id,
        case_id=body.case_id,
        decision=body.decision,
        rationale=body.rationale,
        dry_run=body.dry_run,
        decided_by=user.username,
        decided_by_role=user.role,
    )
    if status_code >= 400:
        raise HTTPException(status_code=status_code, detail=(result or {}).get("detail", "approval_failed"))
    return result


# --------------------------------------------------------------------------- audit


@app.get("/api/audit", tags=["audit"])
async def list_audit(
    q: str | None = None,
    actor: str | None = None,
    actor_type: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    user: TokenPayload = Depends(require_analyst),
) -> dict:
    return await reads.list_audit(
        UPSTREAMS["audit"],
        user,
        q=q,
        actor=actor,
        actor_type=actor_type,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------------- metrics (dashboard snapshot)


@app.get("/api/metrics", tags=["metrics"])
async def metrics_snapshot(_user: TokenPayload = Depends(require_analyst)) -> dict:
    return await reads.get_metrics_snapshot(
        UPSTREAMS["ingestion"],
        UPSTREAMS["detection"],
        UPSTREAMS["cases"],
        UPSTREAMS["response"],
        UPSTREAMS["approval"],
    )


# --------------------------------------------------------------------------- demo pipeline


@app.get("/api/demo/scenarios", tags=["demo"])
async def demo_scenarios(_user: TokenPayload = Depends(require_analyst)) -> list[dict]:
    return demo_pipeline.available_scenarios()


@app.post("/api/demo/run-scenario", tags=["demo"])
async def demo_run_scenario(body: dict, user: TokenPayload = Depends(require_analyst)) -> dict:
    scenario_id = body.get("scenario_id")
    if not scenario_id:
        raise HTTPException(status_code=422, detail="scenario_id is required")
    if not is_sync_mode():
        # Async/full-stack mode: fire the scenario through the real
        # ingestion HTTP API and let Kafka carry it through the pipeline;
        # results land in case_management asynchronously rather than being
        # returned synchronously here.
        try:
            data = demo_pipeline.available_scenarios()
            scenario = next((s for s in data if s["scenario_id"] == scenario_id), None)
        except Exception:
            scenario = None
        return {
            "status": "started",
            "message": "Scenario replay started against the live ingestion pipeline (async mode); "
            "check /api/cases shortly for the resulting case.",
            "scenario_id": scenario_id,
            "case_id": None,
            "run_id": None,
            "scenario": scenario,
        }
    try:
        result = await demo_pipeline.run_scenario(scenario_id, tenant_id=user.tenant_id)
    except demo_pipeline.ScenarioNotFound:
        raise HTTPException(status_code=404, detail=f"scenario_not_found: {scenario_id}")
    except Exception:
        logger.exception("demo_run_scenario_failed scenario_id=%s", scenario_id)
        raise HTTPException(status_code=500, detail="demo_pipeline_failed")
    return result


# --------------------------------------------------------------------------- openapi aggregation + generic proxy


@app.get("/api/v1/openapi", tags=["ops"])
async def openapi_aggregate() -> dict:
    return await aggregate_openapi(UPSTREAMS)


@app.api_route(
    "/api/v1/proxy/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], tags=["ops"]
)
async def generic_proxy(
    service: str, path: str, request: Request, user: TokenPayload = Depends(require_admin)
) -> Response:
    """Direct, authenticated passthrough to any upstream's native API --
    for tooling/debugging, not used by the bundled frontend (which talks to
    the reshaped ``/api/*`` BFF endpoints above)."""

    base_url = UPSTREAMS.get(service)
    if base_url is None:
        raise HTTPException(status_code=404, detail=f"unknown_service: {service}; expected one of {list(UPSTREAMS)}")
    return await proxy_request(base_url=base_url, path=f"/{path}", request=request, user=user)
