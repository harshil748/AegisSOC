"""AegisSOC Response Policy Service.

Recommends playbooks and safe response actions from the fixed action-class
taxonomy (notify, collect_data, create_ticket, quarantine_recommend,
disable_account_recommend, isolate_host_recommend, block_ioc_recommend,
ignore, enrich, escalate) using a playbook catalog blended with an offline,
warm-started LinUCB contextual bandit over historical/analyst feedback.

Every disruptive action defaults to dry_run=True and must pass through the
approval service before any adapter executes it -- this service only ever
*recommends*, it never calls out to execute anything itself.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field

from aegis_common.observability import EVENTS_PROCESSED
from aegis_common.service import create_service_app

from policy_core.bandit import evaluate_offline, get_bandit, load_feedback_log, persist_bandit
from policy_core.objectives import infer_objective
from policy_core.recommend import recommend_action, record_outcome
from policy_core import store as recommendation_store
from policy_core.taxonomy import ALLOWED_ACTIONS_BY_OBJECTIVE, OBJECTIVES, PLAYBOOKS

logger = logging.getLogger("aegis.response_policy")
SERVICE_NAME = "response_policy"


class RecommendRequest(BaseModel):
    case_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    asset_criticality: float = Field(ge=0.0, le=1.0, default=0.5)
    likely_objective: str | None = None
    technique_ids: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    action_id: str | None = None
    action_class: str
    objective: str
    risk_score: float = Field(ge=0.0, le=1.0)
    asset_criticality: float = Field(ge=0.0, le=1.0, default=0.5)
    reward: float = Field(ge=-1.0, le=1.0, description="Analyst-derived reward: +1 correct/helpful, -1 harmful/wrong")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_bandit()  # warm-start on startup so the first request isn't slow
    logger.info("response_policy_started arms=%d", len(OBJECTIVES))
    yield
    persist_bandit()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Playbook + offline contextual-bandit response action recommendations. Recommend-only, never auto-executes.",
    lifespan=lifespan,
)


@app.post("/api/v1/recommend", tags=["recommend"])
async def recommend(req: RecommendRequest) -> dict:
    objective = req.likely_objective or infer_objective(req.technique_ids, req.risk_score)
    if objective not in PLAYBOOKS:
        raise HTTPException(status_code=400, detail=f"unknown objective '{objective}', expected one of {OBJECTIVES}")

    action = recommend_action(
        case_id=req.case_id,
        risk_score=req.risk_score,
        asset_criticality=req.asset_criticality,
        likely_objective=objective,
    )
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="recommend", outcome=action.action_class.value).inc()
    return action.model_dump(mode="json")


@app.get("/api/v1/recommendations", tags=["recommend"])
async def list_recommendations(case_id: str | None = None, status: str | None = None) -> list[dict]:
    return [a.model_dump(mode="json") for a in recommendation_store.list_all(case_id=case_id, status=status)]


@app.get("/api/v1/recommendations/{action_id}", tags=["recommend"])
async def get_recommendation(action_id: str) -> dict:
    action = recommendation_store.get(action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="recommendation not found")
    return action.model_dump(mode="json")


@app.get("/api/v1/playbooks", tags=["playbooks"])
async def list_playbooks() -> dict[str, Any]:
    return {
        "objectives": OBJECTIVES,
        "playbooks": {
            k: {
                "playbook_id": v["playbook_id"],
                "action_class": v["action_class"].value,
                "title": v["title"],
                "risk_if_executed": v["risk_if_executed"].value,
                "allowed_actions": [a.value for a in ALLOWED_ACTIONS_BY_OBJECTIVE.get(k, [])],
            }
            for k, v in PLAYBOOKS.items()
        },
    }


@app.post("/api/v1/feedback", tags=["policy"])
async def submit_feedback(req: FeedbackRequest) -> dict:
    record_outcome(
        action_class=req.action_class,
        risk_score=req.risk_score,
        asset_criticality=req.asset_criticality,
        objective=req.objective,
        reward=req.reward,
    )
    if req.action_id:
        recommendation_store.mark_status(req.action_id, "approved" if req.reward > 0 else "rejected")
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="feedback", outcome="recorded").inc()
    return {"status": "recorded"}


@app.get("/api/v1/policy/evaluate", tags=["policy"])
async def evaluate_policy() -> dict:
    """Offline evaluation of the current bandit policy against the logged
    feedback dataset -- match rate against logged actions and average
    reward, as a sanity check before trusting bandit-driven recommendations."""

    bandit = get_bandit()
    episodes = load_feedback_log()
    return evaluate_offline(bandit, episodes)


@app.get("/api/v1/policy/state", tags=["policy"])
async def policy_state() -> dict:
    bandit = get_bandit()
    return {"pulls": bandit.pulls, "arms": list(bandit.A.keys())}
