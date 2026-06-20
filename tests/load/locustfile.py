"""Load test for the AegisSOC ingestion path.

Run via `make load-test` or directly:
    locust -f tests/load/locustfile.py --headless -u 200 -r 20 -t 5m --host http://localhost:8001

Targets `ingestion` directly (see docs/EVALUATION.md "Load testing") to
measure the data-path's own throughput/latency ceiling, independent of
gateway auth overhead. A lighter profile against the gateway
(GatewayUser, disabled by default — enable with --tags gateway) exercises
analyst-facing API latency under concurrent UI usage.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, tag, task

SOURCES = ["sysmon", "zeek", "suricata", "firewall", "dns", "cloudtrail"]
HOSTS = [f"WIN-LOAD-{i:03d}" for i in range(50)]
USERS = [f"loaduser{i}" for i in range(50)]


def _fake_record() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": random.choice(["process_creation", "network_connection", "logon", "dns_query"]),
        "host": random.choice(HOSTS),
        "user": random.choice(USERS),
        "command_line": random.choice(
            [
                "powershell.exe -Command Get-Process",
                "cmd.exe /c dir",
                "explorer.exe",
                "powershell.exe -EncodedCommand SQBFAFgA",
            ]
        ),
        "src_ip": f"10.1.{random.randint(0, 255)}.{random.randint(1, 254)}",
        "dst_ip": f"8.8.{random.randint(0, 255)}.{random.randint(1, 254)}",
    }


class IngestionUser(HttpUser):
    """Simulates a telemetry connector pushing batches to /v1/ingest."""

    wait_time = between(0.1, 0.5)

    @task
    def ingest_batch(self) -> None:
        batch = {
            "source": random.choice(SOURCES),
            "tenant_id": "default",
            "records": [_fake_record() for _ in range(random.randint(5, 25))],
        }
        self.client.post("/v1/ingest", json=batch)


class GatewayUser(HttpUser):
    """Simulates analyst UI traffic against frontend_gateway. Run with a
    separate `--host http://localhost:8080` invocation.
    """

    wait_time = between(1, 3)

    def on_start(self) -> None:
        resp = self.client.post("/v1/auth/login", json={"username": "analyst", "password": "analyst"})
        self.token = resp.json().get("access_token", "demo-token")

    @tag("gateway")
    @task(3)
    def list_cases(self) -> None:
        self.client.get("/v1/cases/cases", headers={"Authorization": f"Bearer {self.token}"})

    @tag("gateway")
    @task(1)
    def list_approvals(self) -> None:
        self.client.get("/v1/approvals/", headers={"Authorization": f"Bearer {self.token}"})
