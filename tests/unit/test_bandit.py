"""Unit tests for offline LinUCB bandit policy evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "common"))
sys.path.insert(0, str(ROOT / "services" / "response_policy"))

from aegis_common.schema.events import ActionClass  # noqa: E402
from policy_core.bandit import LinUCBBandit, build_context, evaluate_offline  # noqa: E402


def test_bandit_selects_allowed_arm() -> None:
    bandit = LinUCBBandit()
    x = build_context(risk_score=0.9, asset_criticality=0.8, objective="ransomware_impact")
    allowed = [
        ActionClass.ESCALATE.value,
        ActionClass.ISOLATE_HOST_RECOMMEND.value,
        ActionClass.NOTIFY.value,
    ]
    arm, scores = bandit.select(x, allowed_arms=allowed, explore=False)
    assert arm in scores
    assert arm in allowed


def test_bandit_learns_from_reward() -> None:
    bandit = LinUCBBandit()
    x = build_context(risk_score=0.95, asset_criticality=0.9, objective="credential_access")
    escalate = ActionClass.ESCALATE.value
    ignore = ActionClass.IGNORE.value
    for _ in range(20):
        bandit.update(escalate, x, reward=1.0)
        bandit.update(ignore, x, reward=-1.0)
    arm, _ = bandit.select(x, allowed_arms=[escalate, ignore], explore=False)
    assert arm == escalate


def test_offline_evaluation_returns_metrics() -> None:
    bandit = LinUCBBandit()
    episodes = []
    for risk, action, reward in [
        (0.9, ActionClass.ESCALATE.value, 1.0),
        (0.2, ActionClass.IGNORE.value, 0.8),
        (0.7, ActionClass.ENRICH.value, 0.5),
    ]:
        episodes.append(
            {
                "risk_score": risk,
                "asset_criticality": 0.5,
                "objective": "unknown",
                "action_class": action,
                "reward": reward,
            }
        )
        x = build_context(risk, 0.5, "unknown")
        bandit.update(action, x, reward)
    metrics = evaluate_offline(bandit, episodes)
    assert "match_rate" in metrics
    assert "avg_reward_baseline_all_logged" in metrics
    assert 0.0 <= metrics["match_rate"] <= 1.0
