"""Combines the playbook catalog with the contextual bandit to produce a
single ActionRecommendation. Disruptive actions are always dry_run_default
and are never executed here -- only the approval + dry-run SOAR adapters
downstream can ever move an action toward execution."""

from __future__ import annotations

from aegis_common.schema.events import ActionClass, ActionRecommendation, Severity
from aegis_common.utils.helpers import utcnow

from policy_core.bandit import build_context, get_bandit
from policy_core.store import register
from policy_core.taxonomy import ALLOWED_ACTIONS_BY_OBJECTIVE, PLAYBOOKS, is_disruptive


def recommend_action(
    *, case_id: str, risk_score: float, asset_criticality: float, likely_objective: str
) -> ActionRecommendation:
    objective = likely_objective if likely_objective in PLAYBOOKS else ("benign" if risk_score < 0.3 else "recon")
    playbook = PLAYBOOKS[objective]

    bandit = get_bandit()
    x = build_context(risk_score, asset_criticality, objective)
    allowed = [a.value for a in ALLOWED_ACTIONS_BY_OBJECTIVE.get(objective, [])] or None
    chosen_arm, scores = bandit.select(x, allowed_arms=allowed, explore=True)
    action_class = ActionClass(chosen_arm)

    if risk_score < 0.25:
        action_class = ActionClass.IGNORE

    disruptive = is_disruptive(action_class)

    recommendation = ActionRecommendation(
        case_id=case_id,
        action_class=action_class,
        title=playbook["title"] if action_class == playbook["action_class"] else action_class.value.replace("_", " ").title(),
        description=(
            f"Policy recommendation for objective='{objective}', risk_score={risk_score:.2f}, "
            f"asset_criticality={asset_criticality:.2f}. Bandit scores: "
            f"{ {k: round(v, 3) for k, v in scores.items()} }"
        ),
        impact_summary=(
            "Disruptive action: requires analyst/senior_analyst approval before any dry-run execution."
            if disruptive
            else "Non-disruptive action: safe to record and notify without approval; still never auto-executed."
        ),
        risk_if_executed=playbook.get("risk_if_executed", Severity.MEDIUM),
        disruptive=disruptive,
        dry_run_default=True,
        playbook_id=playbook.get("playbook_id"),
        parameters={"objective": objective, "bandit_scores": scores},
        confidence=round(min(0.5 + 0.5 * risk_score, 0.99), 3),
        created_at=utcnow(),
        status="pending" if disruptive else "auto_applied_dry_run",
    )
    register(recommendation)
    return recommendation


def record_outcome(action_class: str, risk_score: float, asset_criticality: float, objective: str, reward: float) -> None:
    """Feeds analyst feedback / observed outcomes back into the bandit."""

    from policy_core.bandit import persist_bandit

    bandit = get_bandit()
    x = build_context(risk_score, asset_criticality, objective)
    if action_class in bandit.A:
        bandit.update(action_class, x, reward)
        persist_bandit()
