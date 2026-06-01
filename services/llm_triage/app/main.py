"""AegisSOC LLM Triage Service.

Evidence-grounded analyst copilot: retrieval tools ONLY (case, alerts,
events, graph neighborhood), PII redaction and prompt-injection defenses
before anything reaches a model, a template-based mock fallback when no
LLM API key is configured, and post-generation output validation that
strips claims not tied to a retrieved evidence_id.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException

from aegis_common.config import Settings
from aegis_common.schema.events import TriageReport
from aegis_common.service import create_service_app

from triage_core.pipeline import gather_evidence, generate_triage_report
from triage_core.tools import HTTPEvidenceTools

settings = Settings()
logger = logging.getLogger("aegis.llm_triage")

SERVICE_NAME = "llm_triage"

CASE_MANAGEMENT_URL = os.getenv("CASE_MANAGEMENT_URL", "http://case_management:8006")
GRAPH_BUILDER_URL = os.getenv("GRAPH_BUILDER_URL", "http://graph_builder:8004")

app = create_service_app(
    service_name=SERVICE_NAME,
    description="Evidence-grounded triage reports with citations; refuses unsupported claims.",
)


@app.post("/api/v1/triage/{case_id}", response_model=TriageReport, tags=["triage"])
async def triage(case_id: str) -> TriageReport:
    tools = HTTPEvidenceTools(CASE_MANAGEMENT_URL, GRAPH_BUILDER_URL)
    case = await tools.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    report = await generate_triage_report(
        case_id=case_id,
        tools=tools,
        llm_enabled=settings.llm_enabled,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        max_evidence_items=settings.llm_max_evidence_items,
    )
    return report


@app.get("/api/v1/evidence/{case_id}", tags=["triage"])
async def evidence(case_id: str) -> dict:
    """Returns the exact evidence set the triage pipeline would retrieve and
    show the model for this case, without generating a report -- lets the
    analyst UI display "what evidence exists" independent of any specific
    triage run."""

    tools = HTTPEvidenceTools(CASE_MANAGEMENT_URL, GRAPH_BUILDER_URL)
    case = await tools.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case_not_found")
    items, _alerts, _flags = await gather_evidence(
        case_id=case_id, tools=tools, max_evidence_items=settings.llm_max_evidence_items
    )
    return {"items": [i.model_dump(mode="json") for i in items]}


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    return {
        "llm_enabled": settings.llm_enabled,
        "has_api_key": bool(settings.openai_api_key),
        "model": settings.llm_model,
        "max_evidence_items": settings.llm_max_evidence_items,
    }
