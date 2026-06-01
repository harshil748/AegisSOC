"""A lightweight, dependency-free "GraphSAGE-ish" anomaly scorer.

Real GraphSAGE learns aggregation weights from labeled data. This demo has
no labeled attack corpus to train on, so instead of pulling in PyTorch
Geometric for an untrained model, we implement the *same computational
shape* -- self features concatenated with a mean-aggregated neighborhood
embedding, pushed through a weight matrix and a nonlinearity -- using numpy
with hand-set, monotonic-by-design weights. This keeps inference cheap and
dependency-light (no torch needed in the container) while leaving a single
``_W1``/``_W2`` array to swap in real learned weights later, e.g. after
offline training on analyst-labeled alerts (see README "Scalability path").
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "asset_criticality",
    "degree_norm",
    "rare_edge_score",
    "path_to_bad_norm",
    "intel_hits_norm",
    "technique_diversity_norm",
    "event_rate_norm",
]

# Self-feature transform + neighbor-aggregate transform, concatenated then
# summed (equivalent to SAGE's mean-aggregator + linear layer). Weights are
# hand-set positive priors reflecting known risk direction per feature.
_W_SELF = np.array([0.9, 0.6, 0.7, 0.8, 1.0, 0.5, 0.4])
_W_NEIGHBOR = np.array([0.5, 0.4, 0.5, 0.6, 0.7, 0.3, 0.2])
_BIAS = -1.2


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def build_feature_vector(
    *,
    asset_criticality: float,
    degree: int,
    rare_edge_score: float,
    path_length_to_known_bad: int | None,
    intel_hit_count: int,
    distinct_techniques_window: int,
    event_count_window: int,
) -> np.ndarray:
    degree_norm = min(degree / 20.0, 1.0)
    if path_length_to_known_bad is None:
        path_to_bad_norm = 0.0
    else:
        path_to_bad_norm = max(0.0, 1.0 - (path_length_to_known_bad / 4.0))
    intel_hits_norm = min(intel_hit_count / 3.0, 1.0)
    technique_diversity_norm = min(distinct_techniques_window / 5.0, 1.0)
    event_rate_norm = min(event_count_window / 20.0, 1.0)

    return np.array(
        [
            asset_criticality,
            degree_norm,
            rare_edge_score,
            path_to_bad_norm,
            intel_hits_norm,
            technique_diversity_norm,
            event_rate_norm,
        ]
    )


def score(
    self_features: np.ndarray,
    neighbor_features: np.ndarray | None = None,
) -> float:
    """GraphSAGE-shaped forward pass: self-transform + mean-neighbor-transform -> sigmoid."""

    neighbor = neighbor_features if neighbor_features is not None else self_features * 0.6
    z = float(np.dot(_W_SELF, self_features) + np.dot(_W_NEIGHBOR, neighbor) + _BIAS)
    return round(_sigmoid(z), 4)


def score_from_features(features: dict) -> float:
    vec = build_feature_vector(
        asset_criticality=features.get("asset_criticality", 0.3),
        degree=features.get("degree", 0),
        rare_edge_score=features.get("rare_edge_score", 0.5),
        path_length_to_known_bad=features.get("path_length_to_known_bad"),
        intel_hit_count=features.get("intel_hit_count", 0),
        distinct_techniques_window=features.get("distinct_techniques_window", 0),
        event_count_window=features.get("event_count_window", 0),
    )
    return score(vec)
