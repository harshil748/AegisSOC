"""Best-effort OpenAPI aggregation across every upstream service.

Rather than attempting a lossy merge of eleven independent OpenAPI documents
into one (path collisions, incompatible ``components/schemas`` names, etc.),
this fetches each upstream's own ``/openapi.json`` and returns them keyed by
service name alongside a flat path index -- enough for a docs UI (e.g.
Redoc/Swagger multi-spec selector, or the AegisSOC frontend's API explorer)
to link straight through to each service's real, accurate spec.
"""

from __future__ import annotations

import asyncio
from typing import Any

from gateway_core.proxy import fetch_json


async def aggregate_openapi(upstreams: dict[str, str]) -> dict[str, Any]:
    names = list(upstreams.keys())
    specs = await asyncio.gather(
        *(fetch_json(upstreams[name], "/openapi.json") for name in names)
    )

    services: dict[str, Any] = {}
    path_index: list[dict[str, str]] = []
    for name, spec in zip(names, specs):
        if spec is None:
            services[name] = {"available": False, "base_url": upstreams[name]}
            continue
        services[name] = {
            "available": True,
            "base_url": upstreams[name],
            "title": spec.get("info", {}).get("title"),
            "version": spec.get("info", {}).get("version"),
            "spec": spec,
        }
        for path, methods in (spec.get("paths") or {}).items():
            for method in methods:
                path_index.append({"service": name, "method": method.upper(), "path": path})

    return {
        "gateway": "AegisSOC Gateway",
        "aggregated_services": len([s for s in services.values() if s.get("available")]),
        "total_services": len(names),
        "services": services,
        "path_index": sorted(path_index, key=lambda p: (p["service"], p["path"])),
    }
