#!/usr/bin/env python3
"""Generate N synthetic events/sec against the ingestion API for load testing.

Draws events from the existing data/samples/*.jsonl corpus (cycling through
sources round-robin) and fires them at the ingestion API using a thread pool,
reporting throughput, latency percentiles, and error rate. Falls back to a
local-only "generation rate" benchmark (no network) if no ingestion API is
reachable, so the script is still useful before services/ingestion exists.

Usage:
    python scripts/load_test_ingest.py --rate 200 --duration 30
    python scripts/load_test_ingest.py --rate 500 --duration 10 --api-url http://localhost:8080
    python scripts/load_test_ingest.py --rate 1000 --duration 15 --workers 32 --dry-run
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import replay_scenario  # noqa: E402  (reuse discover_api_base)

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = Path(__file__).parent.parent
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
INGEST_PATH = "/api/v1/ingest"


def load_corpus(samples_dir: Path) -> list[dict]:
    events = []
    for path in sorted(samples_dir.glob("*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    if not events:
        raise SystemExit(f"No sample events found in {samples_dir}. Run scripts/generate_samples.py first.")
    return events


def send_one(base_url: str, tenant_id: str, event: dict) -> tuple[bool, float]:
    payload = {
        "tenant_id": tenant_id,
        "source": event.get("source"),
        "timestamp": event.get("timestamp"),
        "raw": event.get("event", event.get("raw", {})),
    }
    start = time.perf_counter()
    try:
        resp = requests.post(f"{base_url}{INGEST_PATH}", json=payload, timeout=5)
        ok = resp.status_code < 300
    except requests.RequestException:
        ok = False
    return ok, time.perf_counter() - start


def run_load_test(base_url: str | None, tenant_id: str, corpus: list[dict], rate: float, duration: float, workers: int) -> None:
    cycle = itertools.cycle(corpus)
    interval = 1.0 / rate if rate > 0 else 0.0
    target_total = int(rate * duration)

    latencies: list[float] = []
    successes = 0
    failures = 0
    sent = 0

    print(f"Target: {rate:.0f} events/sec for {duration:.0f}s (~{target_total} events), workers={workers}")
    print(f"Mode: {'LIVE against ' + base_url if base_url else 'local generation-rate benchmark (no ingestion API reachable)'}\n")

    executor = ThreadPoolExecutor(max_workers=workers) if base_url else None
    futures = []
    start_time = time.perf_counter()
    next_tick = start_time

    while time.perf_counter() - start_time < duration:
        event = next(cycle)
        if base_url:
            futures.append(executor.submit(send_one, base_url, tenant_id, event))
        sent += 1
        next_tick += interval
        sleep_for = next_tick - time.perf_counter()
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed = time.perf_counter() - start_time

    if executor:
        for fut in futures:
            ok, latency = fut.result()
            latencies.append(latency)
            successes += int(ok)
            failures += int(not ok)
        executor.shutdown(wait=True)
    else:
        successes = sent  # local benchmark: "success" == generated/serialized in time

    actual_rate = sent / elapsed if elapsed else 0.0
    print("=== Load test results ===")
    print(f"  events attempted:   {sent}")
    print(f"  elapsed:            {elapsed:.2f}s")
    print(f"  actual throughput:  {actual_rate:.1f} events/sec (target {rate:.0f}/sec)")
    if base_url:
        print(f"  successes/failures: {successes}/{failures} ({(failures / sent * 100) if sent else 0:.2f}% error rate)")
        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95) - 1]
            p99 = latencies[int(len(latencies) * 0.99) - 1]
            print(f"  latency p50/p95/p99: {p50*1000:.1f}ms / {p95*1000:.1f}ms / {p99*1000:.1f}ms")
            print(f"  latency mean/stdev:  {statistics.mean(latencies)*1000:.1f}ms / {statistics.pstdev(latencies)*1000:.1f}ms")
    else:
        print("  (no network calls made -- this measures corpus-cycling overhead only)")
        print("  Start services/ingestion and re-run with --api-url to get real latency/error numbers.")

    print(f"\n  extrapolated daily volume at this rate: {actual_rate * 86400:,.0f} events/day")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rate", type=float, default=100.0, help="target events/sec")
    parser.add_argument("--duration", type=float, default=15.0, help="test duration in seconds")
    parser.add_argument("--workers", type=int, default=16, help="thread-pool size for concurrent POSTs")
    parser.add_argument("--api-url", default=None)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--samples-dir", default=str(SAMPLES_DIR))
    parser.add_argument("--dry-run", action="store_true", help="skip API discovery entirely, local benchmark only")
    args = parser.parse_args()

    if requests is None and not args.dry_run:
        print("`requests` is not installed; running local-only benchmark. `pip install requests` for live load testing.")
        args.dry_run = True

    base_url = None if args.dry_run else replay_scenario.discover_api_base(args.api_url)
    corpus = load_corpus(Path(args.samples_dir))
    print(f"Loaded {len(corpus)} candidate events from {args.samples_dir}\n")

    run_load_test(base_url, args.tenant_id, corpus, args.rate, args.duration, args.workers)


if __name__ == "__main__":
    main()
