"""Offline contextual bandit (LinUCB) over the safe action-class taxonomy.

Trained/warm-started from a small logged-feedback dataset
(``data/policy/feedback_log.json``) rather than online exploration against
real production traffic -- consistent with "introduce RL/bandit policies
cautiously and evaluate offline first" (see docs "Scalability path" /
README). State persists to a JSON file so recommendations are stable across
restarts and further updateable as analyst feedback arrives via
case_management.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np

from aegis_common.schema.events import ActionClass

from policy_core.taxonomy import ALLOWED_ACTIONS_BY_OBJECTIVE, OBJECTIVES

logger = logging.getLogger("aegis.response_policy.bandit")

ARMS = [a.value for a in ActionClass]
FEATURE_DIM = 3 + len(OBJECTIVES)  # [bias, risk_score, asset_criticality] + one-hot(objective)
ALPHA = 0.6  # exploration coefficient


def data_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data")) / "policy"


def build_context(risk_score: float, asset_criticality: float, objective: str) -> np.ndarray:
    one_hot = [1.0 if objective == o else 0.0 for o in OBJECTIVES]
    return np.array([1.0, risk_score, asset_criticality, *one_hot])


class LinUCBBandit:
    def __init__(self, dim: int = FEATURE_DIM, alpha: float = ALPHA) -> None:
        self.dim = dim
        self.alpha = alpha
        self.A: dict[str, np.ndarray] = {arm: np.eye(dim) for arm in ARMS}
        self.b: dict[str, np.ndarray] = {arm: np.zeros(dim) for arm in ARMS}
        self.pulls: dict[str, int] = {arm: 0 for arm in ARMS}

    def theta(self, arm: str) -> np.ndarray:
        return np.linalg.solve(self.A[arm], self.b[arm])

    def score(self, arm: str, x: np.ndarray, explore: bool = True) -> float:
        A_inv = np.linalg.inv(self.A[arm])
        theta = A_inv @ self.b[arm]
        mean = float(theta @ x)
        if not explore:
            return mean
        bonus = self.alpha * float(np.sqrt(x @ A_inv @ x))
        return mean + bonus

    def select(self, x: np.ndarray, allowed_arms: list[str] | None = None, explore: bool = True) -> tuple[str, dict[str, float]]:
        candidates = allowed_arms or ARMS
        scores = {arm: self.score(arm, x, explore=explore) for arm in candidates}
        best = max(scores, key=scores.get)
        return best, scores

    def update(self, arm: str, x: np.ndarray, reward: float) -> None:
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x
        self.pulls[arm] += 1

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "A": {arm: self.A[arm].tolist() for arm in ARMS},
            "b": {arm: self.b[arm].tolist() for arm in ARMS},
            "pulls": self.pulls,
        }
        path.write_text(json.dumps(state))

    @classmethod
    def load_or_new(cls, path: Path) -> "LinUCBBandit":
        bandit = cls()
        if path.exists():
            try:
                state = json.loads(path.read_text())
                for arm in ARMS:
                    if arm in state.get("A", {}):
                        bandit.A[arm] = np.array(state["A"][arm])
                        bandit.b[arm] = np.array(state["b"][arm])
                        bandit.pulls[arm] = state.get("pulls", {}).get(arm, 0)
                return bandit
            except Exception:
                logger.exception("failed_to_load_bandit_state_starting_fresh")
        return bandit


def load_feedback_log() -> list[dict]:
    path = data_dir() / "feedback_log.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def warm_start(bandit: LinUCBBandit, episodes: list[dict]) -> int:
    count = 0
    for ep in episodes:
        x = build_context(ep["risk_score"], ep["asset_criticality"], ep["objective"])
        if ep["action_class"] in bandit.A:
            bandit.update(ep["action_class"], x, ep["reward"])
            count += 1
    return count


def evaluate_offline(bandit: LinUCBBandit, episodes: list[dict]) -> dict:
    """Off-policy-ish evaluation: how often would the *current greedy* policy
    match the logged action, and what reward did those matching episodes see,
    versus the unconditional average logged reward (baseline)."""

    if not episodes:
        return {"episodes": 0}

    matched_rewards = []
    all_rewards = []
    action_distribution: dict[str, int] = {}
    for ep in episodes:
        x = build_context(ep["risk_score"], ep["asset_criticality"], ep["objective"])
        allowed = [a.value for a in ALLOWED_ACTIONS_BY_OBJECTIVE.get(ep["objective"], [])] or None
        chosen, _ = bandit.select(x, allowed_arms=allowed, explore=False)
        action_distribution[chosen] = action_distribution.get(chosen, 0) + 1
        all_rewards.append(ep["reward"])
        if chosen == ep["action_class"]:
            matched_rewards.append(ep["reward"])

    return {
        "episodes": len(episodes),
        "policy_action_distribution": action_distribution,
        "match_rate": round(len(matched_rewards) / len(episodes), 3),
        "avg_reward_when_policy_matches_log": round(float(np.mean(matched_rewards)), 3) if matched_rewards else None,
        "avg_reward_baseline_all_logged": round(float(np.mean(all_rewards)), 3),
    }


_bandit: LinUCBBandit | None = None


def get_bandit() -> LinUCBBandit:
    global _bandit
    if _bandit is None:
        path = data_dir() / "bandit_state.json"
        _bandit = LinUCBBandit.load_or_new(path)
        if all(count == 0 for count in _bandit.pulls.values()):
            warm_start(_bandit, load_feedback_log())
            _bandit.save(path)
    return _bandit


def persist_bandit() -> None:
    if _bandit is not None:
        _bandit.save(data_dir() / "bandit_state.json")
