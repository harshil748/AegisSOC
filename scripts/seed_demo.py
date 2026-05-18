#!/usr/bin/env python3
"""One-shot demo seeding: load threat intel/assets, replay all 3 canonical
scenarios, and print the resulting case IDs.

This is the "make it demoable in one command" script for AegisSOC. It:
  1. Loads data/intel/*.json (KEV, MISP IOCs, asset inventory, identity map)
     and POSTs them to the enrichment API if reachable, else reports counts.
  2. Replays each scenario in data/scenarios/ in a sensible demo order
     (benign first so reviewers see a clean/low-risk baseline, then the
     critical attack chain, then the repeat-infrastructure scenario).
  3. Polls the case-management API for a resulting case, if reachable.
     If no backend is running yet, generates a deterministic *simulated*
     case ID so the demo script is still useful pre-integration, and labels
     it clearly as such.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --api-url http://localhost:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import replay_scenario  # noqa: E402

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = Path(__file__).parent.parent
INTEL_DIR = REPO_ROOT / "data" / "intel"
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"

DEMO_ORDER = [
    "benign_admin_false_positive.json",
    "phishing_ransomware_chain.json",
    "repeat_attacker_infra.json",
]

INTEL_ENDPOINTS = {
    "cisa_kev_sample.json": "/api/v1/intel/kev",
    "misp_iocs.json": "/api/v1/intel/iocs",
    "asset_inventory.json": "/api/v1/assets",
    "identity_map.json": "/api/v1/identities",
}

CASE_NAMESPACE = uuid.UUID("6f6d3f3a-a1e1-50c0-8888-000000000001")


def load_intel(base_url: str | None, tenant_id: str) -> None:
    print("=== Loading threat intel & asset context ===")
    for filename, endpoint in INTEL_ENDPOINTS.items():
        path = INTEL_DIR / filename
        if not path.exists():
            print(f"  ! missing {filename}")
            continue
        data = json.loads(path.read_text())
        count = len(data.get("indicators") or data.get("vulnerabilities") or data.get("hosts") or data.get("identities") or [])
        if base_url and requests is not None:
            try:
                resp = requests.post(f"{base_url}{endpoint}", json={"tenant_id": tenant_id, "payload": data}, timeout=5)
                status = "loaded" if resp.status_code < 300 else f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                status = f"unreachable ({exc.__class__.__name__})"
        else:
            status = "local-only (no ingestion API reachable)"
        print(f"  {filename:28s} {count:4d} records -> {status}")


def try_fetch_case_id(base_url: str | None, scenario_id: str, tenant_id: str) -> tuple[str, bool]:
    """Returns (case_id, is_real). Falls back to a deterministic simulated ID."""
    if base_url and requests is not None:
        try:
            resp = requests.get(
                f"{base_url}/api/v1/cases",
                params={"tenant_id": tenant_id, "scenario_id": scenario_id},
                timeout=5,
            )
            if resp.status_code < 300:
                body = resp.json()
                cases = body.get("cases") or body.get("items") or []
                if cases:
                    return cases[0].get("case_id", cases[0]), True
        except requests.RequestException:
            pass
    simulated = str(uuid.uuid5(CASE_NAMESPACE, f"{tenant_id}:{scenario_id}"))
    return f"SIM-{simulated[:8].upper()}", False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--speed", type=float, default=200.0, help="scenario replay speed multiplier")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=2.0, help="wait after each replay for detection/enrichment to catch up")
    args = parser.parse_args()

    base_url = None
    if not args.dry_run:
        base_url = replay_scenario.discover_api_base(args.api_url)
        print(f"Ingestion API: {base_url or 'not reachable -> running in local/simulated mode'}\n")

    load_intel(base_url, args.tenant_id)

    print("\n=== Replaying demo scenarios ===")
    results = []
    for filename in DEMO_ORDER:
        path = SCENARIOS_DIR / filename
        if not path.exists():
            print(f"  ! missing scenario {filename}")
            continue
        summary = replay_scenario.replay_file(path, base_url, args.tenant_id, args.speed, args.dry_run)
        time.sleep(args.settle_seconds if base_url else 0)
        case_id, is_real = try_fetch_case_id(base_url, summary["scenario_id"], args.tenant_id)
        summary["case_id"] = case_id
        summary["case_id_is_real"] = is_real
        results.append(summary)

    print("\n=== Seed summary ===")
    print(f"{'scenario_id':32s} {'case_id':24s} {'severity':10s} {'min_risk':9s} {'source'}")
    for r in results:
        source = "case-management API" if r["case_id_is_real"] else "simulated (no backend reachable)"
        print(f"{r['scenario_id']:32s} {r['case_id']:24s} {str(r['expected_severity']):10s} "
              f"{str(r['expected_min_risk']):9s} {source}")

    print("\nDone. Re-run with --api-url once services/ingestion and services/case_management are live "
          "to replace simulated case IDs with real ones.")


if __name__ == "__main__":
    main()
