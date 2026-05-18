#!/usr/bin/env python3
"""Run the AegisSOC gateway in sync mode (no Kafka/Postgres/Neo4j required).

Usage:
  AEGIS_SYNC_MODE=true python scripts/run_sync_gateway.py

Then open the frontend (`cd frontend && npm run dev`) against http://localhost:8080
or hit POST /api/demo/run-scenario directly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("AEGIS_SYNC_MODE", "true")
os.environ.setdefault("LLM_ENABLED", "true")

for rel in [
    "packages/common",
    "services/frontend_gateway",
    "services/normalization",
    "services/enrichment",
    "services/graph_builder",
    "services/detection",
    "services/case_management",
    "services/llm_triage",
    "services/response_policy",
    "services/ingestion",
    "services/approval",
    "services/audit",
]:
    sys.path.insert(0, str(ROOT / rel))

import uvicorn


def main() -> None:
    print("Starting AegisSOC frontend_gateway in SYNC mode on :8080")
    print("Demo users: analyst/analyst123, senior/senior123, admin/admin123")
    print("Try: POST http://localhost:8080/api/demo/run-scenario {\"scenario_id\":\"phishing_ransomware_chain\"}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False, app_dir=str(ROOT / "services" / "frontend_gateway"))


if __name__ == "__main__":
    main()
