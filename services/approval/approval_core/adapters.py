"""Dry-run SOAR adapters.

Every adapter here is a *simulation* of what a real SOAR/EDR/IAM/ticketing
integration would do. None of them make an external network call or mutate
any real system -- that is intentional: AegisSOC recommends and simulates,
it does not autonomously execute disruptive actions. A genuinely "live"
adapter (e.g. a real EDR quarantine API call) is exactly the kind of
enterprise connector that is out of scope here and would be swapped in
behind this same interface, gated by an explicit non-dry-run flag that
does not exist in this build.

Each adapter returns a JSON-serializable result dict and, where the
action is conceptually reversible, a ``rollback_token`` that
``rollback_action`` can use to simulate an undo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

AdapterFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sim_ref(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


async def adapter_notify(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter": "notify",
        "external_system": "slack_sim",
        "external_ref": _sim_ref("SLK"),
        "status": "success",
        "message": f"[DRY-RUN] Would notify #soc-alerts about case {ctx.get('case_id')}: {ctx.get('title')}",
        "rollback_supported": False,
        "simulated_at": _now(),
    }


async def adapter_create_ticket(ctx: dict[str, Any]) -> dict[str, Any]:
    ticket_ref = _sim_ref("JIRA")
    return {
        "adapter": "create_ticket",
        "external_system": "jira_sim",
        "external_ref": ticket_ref,
        "status": "success",
        "message": f"[DRY-RUN] Would create ticket {ticket_ref} for case {ctx.get('case_id')}",
        "rollback_supported": True,
        "rollback_token": ticket_ref,
        "simulated_at": _now(),
    }


async def adapter_quarantine_host(ctx: dict[str, Any]) -> dict[str, Any]:
    host = ctx.get("parameters", {}).get("host_id", "unknown-host")
    token = _sim_ref("EDR-QRT")
    return {
        "adapter": "quarantine_host",
        "external_system": "edr_sim",
        "external_ref": token,
        "status": "success",
        "message": f"[DRY-RUN] Would quarantine host '{host}' via EDR (network isolation policy applied)",
        "rollback_supported": True,
        "rollback_token": token,
        "simulated_at": _now(),
    }


async def adapter_isolate_host(ctx: dict[str, Any]) -> dict[str, Any]:
    host = ctx.get("parameters", {}).get("host_id", "unknown-host")
    token = _sim_ref("EDR-ISO")
    return {
        "adapter": "isolate_host",
        "external_system": "edr_sim",
        "external_ref": token,
        "status": "success",
        "message": f"[DRY-RUN] Would isolate host '{host}' from the network via EDR containment",
        "rollback_supported": True,
        "rollback_token": token,
        "simulated_at": _now(),
    }


async def adapter_disable_account(ctx: dict[str, Any]) -> dict[str, Any]:
    user = ctx.get("parameters", {}).get("user_id", "unknown-user")
    token = _sim_ref("IAM-DIS")
    return {
        "adapter": "disable_account",
        "external_system": "iam_sim",
        "external_ref": token,
        "status": "success",
        "message": f"[DRY-RUN] Would disable account '{user}' in IAM/AD and revoke active sessions",
        "rollback_supported": True,
        "rollback_token": token,
        "simulated_at": _now(),
    }


async def adapter_block_ioc(ctx: dict[str, Any]) -> dict[str, Any]:
    ioc = ctx.get("parameters", {}).get("indicator", "unknown-ioc")
    token = _sim_ref("FW-BLK")
    return {
        "adapter": "block_ioc",
        "external_system": "firewall_proxy_sim",
        "external_ref": token,
        "status": "success",
        "message": f"[DRY-RUN] Would push a block rule for indicator '{ioc}' to firewall/proxy",
        "rollback_supported": True,
        "rollback_token": token,
        "simulated_at": _now(),
    }


async def adapter_collect_data(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter": "collect_data",
        "external_system": "edr_forensics_sim",
        "external_ref": _sim_ref("COLLECT"),
        "status": "success",
        "message": f"[DRY-RUN] Would collect forensic triage package for case {ctx.get('case_id')}",
        "rollback_supported": False,
        "simulated_at": _now(),
    }


async def adapter_enrich(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter": "enrich",
        "external_system": "threat_intel_sim",
        "external_ref": _sim_ref("ENRICH"),
        "status": "success",
        "message": "[DRY-RUN] Would request additional threat-intel enrichment for case entities",
        "rollback_supported": False,
        "simulated_at": _now(),
    }


async def adapter_escalate(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter": "escalate",
        "external_system": "pagerduty_sim",
        "external_ref": _sim_ref("PD"),
        "status": "success",
        "message": f"[DRY-RUN] Would page on-call senior analyst for case {ctx.get('case_id')}",
        "rollback_supported": False,
        "simulated_at": _now(),
    }


async def adapter_ignore(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter": "ignore",
        "external_system": "none",
        "external_ref": None,
        "status": "success",
        "message": "No-op: recommendation was to take no action.",
        "rollback_supported": False,
        "simulated_at": _now(),
    }


ADAPTERS: dict[str, AdapterFn] = {
    "notify": adapter_notify,
    "create_ticket": adapter_create_ticket,
    "quarantine_recommend": adapter_quarantine_host,
    "isolate_host_recommend": adapter_isolate_host,
    "disable_account_recommend": adapter_disable_account,
    "block_ioc_recommend": adapter_block_ioc,
    "collect_data": adapter_collect_data,
    "enrich": adapter_enrich,
    "escalate": adapter_escalate,
    "ignore": adapter_ignore,
}


async def run_adapter(action_class: str, ctx: dict[str, Any]) -> dict[str, Any]:
    adapter = ADAPTERS.get(action_class)
    if adapter is None:
        return {
            "adapter": "unknown",
            "external_system": "none",
            "status": "failed",
            "message": f"No dry-run adapter registered for action_class='{action_class}'",
            "rollback_supported": False,
            "simulated_at": _now(),
        }
    return await adapter(ctx)


async def rollback_action(action_class: str, rollback_token: str | None, result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("rollback_supported") or not rollback_token:
        return {
            "status": "unsupported",
            "message": f"Action '{action_class}' has no rollback support or was never executed with a rollback token.",
            "simulated_at": _now(),
        }
    return {
        "status": "success",
        "message": f"[DRY-RUN] Would reverse action '{action_class}' referenced by token {rollback_token}",
        "external_ref": rollback_token,
        "simulated_at": _now(),
    }
