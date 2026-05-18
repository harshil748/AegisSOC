#!/usr/bin/env python3
"""Replay a demo scenario by posting its raw events to the ingestion API.

Reads a scenario JSON file (see data/scenarios/) and POSTs each event, in
timestamp order and with realistic inter-event pacing, to the AegisSOC
ingestion API. Tries http://localhost:8080 first, then http://localhost:8001,
unless --api-url is given explicitly. If no ingestion API is reachable, falls
back to a local dry-run mode that prints what would have been sent -- this
keeps the script useful before the ingestion-service is stood up.

Usage:
    python scripts/replay_scenario.py data/scenarios/phishing_ransomware_chain.json
    python scripts/replay_scenario.py data/scenarios/*.json --speed 50
    python scripts/replay_scenario.py data/scenarios/repeat_attacker_infra.json --api-url http://localhost:8080 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # dry-run still works without requests installed

DEFAULT_CANDIDATE_PORTS = [8080, 8001]
INGEST_PATH = "/api/v1/ingest"
HEALTH_PATH = "/healthz"


def discover_api_base(explicit_url: str | None, timeout: float = 1.5) -> str | None:
    if explicit_url:
        return explicit_url.rstrip("/")
    if requests is None:
        return None
    for port in DEFAULT_CANDIDATE_PORTS:
        base = f"http://localhost:{port}"
        for path in (HEALTH_PATH, "/", INGEST_PATH):
            try:
                resp = requests.get(base + path, timeout=timeout)
                if resp.status_code < 500:
                    return base
            except requests.RequestException:
                continue
    return None


def parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def post_event(base_url: str, tenant_id: str, event: dict, scenario_id: str) -> bool:
    payload = {
        "tenant_id": tenant_id,
        "source": event.get("source"),
        "timestamp": event.get("timestamp"),
        "raw": event.get("raw", event.get("event", {})),
        "replay_metadata": {"scenario_id": scenario_id, "replayed_at": datetime.now(timezone.utc).isoformat()},
    }
    try:
        resp = requests.post(f"{base_url}{INGEST_PATH}", json=payload, timeout=5)
        return resp.status_code < 300
    except requests.RequestException as exc:
        print(f"    ! POST failed: {exc}", file=sys.stderr)
        return False


def replay_file(path: Path, base_url: str | None, tenant_id: str, speed: float, dry_run: bool) -> dict[str, Any]:
    scenario = json.loads(path.read_text())
    events = sorted(scenario["events"], key=lambda e: parse_ts(e["timestamp"]))
    print(f"\n=== Replaying {scenario['scenario_id']} ({len(events)} events) from {path.name} ===")
    print(f"    {scenario.get('name', '')}")

    live = not dry_run and base_url is not None
    sent, failed = 0, 0
    prev_ts = None
    for i, event in enumerate(events, start=1):
        ts = parse_ts(event["timestamp"])
        if live and prev_ts is not None and speed > 0:
            gap = max(0.0, (ts - prev_ts) / speed)
            time.sleep(min(gap, 2.0))  # cap so a demo doesn't literally wait 30 minutes
        prev_ts = ts

        source = event.get("source")
        if not live:
            print(f"  [{i:2d}/{len(events)}] (dry-run) {event['timestamp']}  source={source}")
            sent += 1
            continue

        ok = post_event(base_url, tenant_id, event, scenario["scenario_id"])
        status = "ok" if ok else "FAILED"
        print(f"  [{i:2d}/{len(events)}] {event['timestamp']}  source={source:12s} -> {status}")
        sent += int(ok)
        failed += int(not ok)

    return {
        "scenario_id": scenario["scenario_id"],
        "events_total": len(events),
        "events_sent": sent,
        "events_failed": failed,
        "expected_severity": scenario.get("expected_severity"),
        "expected_min_risk": scenario.get("expected_min_risk"),
        "expected_techniques": scenario.get("expected_techniques"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario_files", nargs="+", help="path(s) to scenario JSON file(s)")
    parser.add_argument("--api-url", default=None, help="ingestion API base URL, e.g. http://localhost:8080")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--speed", type=float, default=60.0, help="playback speed multiplier (60 = 1 real minute per scenario second)")
    parser.add_argument("--dry-run", action="store_true", help="print events instead of POSTing them")
    args = parser.parse_args()

    base_url = None
    if not args.dry_run:
        base_url = discover_api_base(args.api_url)
        if base_url:
            print(f"Ingestion API reachable at {base_url}")
        else:
            print("No ingestion API reachable on localhost:8080 or :8001 -- falling back to dry-run output.")
            print("(Start services/ingestion, or pass --api-url, to actually publish events.)")

    results = []
    for pattern in args.scenario_files:
        for path in sorted(Path().glob(pattern)) if any(c in pattern for c in "*?[]") else [Path(pattern)]:
            if not path.exists():
                print(f"Skipping missing file: {path}", file=sys.stderr)
                continue
            results.append(replay_file(path, base_url, args.tenant_id, args.speed, args.dry_run))

    print("\n=== Replay summary ===")
    for r in results:
        print(f"  {r['scenario_id']:32s} sent={r['events_sent']:3d} failed={r['events_failed']:3d} "
              f"expected_severity={r['expected_severity']} expected_min_risk={r['expected_min_risk']}")


if __name__ == "__main__":
    main()
