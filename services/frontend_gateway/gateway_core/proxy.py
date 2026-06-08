"""Reverse-proxy helper: forwards a request to an upstream service, injecting
the trusted ``X-Aegis-*`` identity headers that internal services use for
RBAC instead of re-verifying the JWT themselves (see
``aegis_common.auth.rbac.current_user_dependency``)."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import Request, Response

from aegis_common.auth.jwt import TokenPayload


async def proxy_request(
    *,
    base_url: str,
    path: str,
    request: Request,
    user: TokenPayload | None,
    timeout: float = 15.0,
) -> Response:
    headers: dict[str, str] = {}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type
    if user is not None:
        headers["X-Aegis-User"] = user.username
        headers["X-Aegis-Role"] = user.role
        headers["X-Aegis-Tenant"] = user.tenant_id

    body = await request.body()
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            resp = await client.request(
                request.method,
                path,
                content=body or None,
                params=dict(request.query_params),
                headers=headers,
            )
        except httpx.RequestError as exc:
            return Response(
                content=f'{{"detail": "upstream_unreachable: {exc}"}}',
                status_code=503,
                media_type="application/json",
            )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def fetch_json(
    base_url: str, path: str, *, params: dict[str, Any] | None = None, timeout: float = 5.0
) -> Any | None:
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            resp = await client.get(path, params=params)
            if resp.status_code >= 400:
                return None
            return resp.json()
        except (httpx.RequestError, ValueError):
            return None


async def post_json(
    base_url: str, path: str, *, json_body: dict[str, Any] | None = None, timeout: float = 10.0
) -> tuple[int, Any | None]:
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        try:
            resp = await client.post(path, json=json_body)
            try:
                body = resp.json()
            except ValueError:
                body = None
            return resp.status_code, body
        except httpx.RequestError as exc:
            return 503, {"detail": f"upstream_unreachable: {exc}"}
