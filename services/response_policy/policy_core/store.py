"""In-process recommendation registry.

Shared by ``policy_core.recommend`` (which registers every recommendation it
produces) and the standalone service's HTTP API. Keeping this in
``policy_core`` rather than in ``app/main.py`` means the frontend_gateway's
sync-mode demo orchestrator -- which calls ``policy_core.recommend_action``
directly, in-process, without going through the HTTP layer at all -- writes
into the exact same registry the ``GET /api/v1/recommendations`` endpoint
reads from.
"""

from __future__ import annotations

from aegis_common.schema.events import ActionRecommendation

_recommendations: dict[str, ActionRecommendation] = {}


def register(action: ActionRecommendation) -> None:
    _recommendations[action.action_id] = action


def get(action_id: str) -> ActionRecommendation | None:
    return _recommendations.get(action_id)


def list_all(case_id: str | None = None, status: str | None = None) -> list[ActionRecommendation]:
    values = list(_recommendations.values())
    if case_id:
        values = [a for a in values if a.case_id == case_id]
    if status:
        values = [a for a in values if a.status == status]
    return sorted(values, key=lambda a: a.created_at, reverse=True)


def mark_status(action_id: str, status: str) -> None:
    action = _recommendations.get(action_id)
    if action is not None:
        action.status = status
