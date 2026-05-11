# ADR 0003: Reinforcement Learning Is Introduced Cautiously and Evaluated Offline First

## Status
Accepted

## Context
The response layer needs to pick an action (ignore, enrich, escalate,
notify, create case, isolate-recommend, disable-account-recommend, ...)
given the current state of a case. This is naturally framed as a
sequential decision problem, which makes RL an attractive long-term
approach: rewards for stopping attacks and reducing analyst burden,
penalties for false positives and business disruption.

However, RL — especially online RL against a live SOC — carries serious
risks for an internship-scale, safety-critical project:

- An **online** policy that explores by taking real actions in a live
  environment could recommend a genuinely harmful action (e.g.
  isolate-recommend on a production database host) while still learning.
- RL reward shaping for "stopped an attack" is very hard to get right
  without a live red team or extensive historical ground truth — a
  poorly shaped reward can be gamed trivially (e.g. maximize reward by
  recommending `ignore` on everything if false-positive penalty
  dominates).
- There is no safe way to online-train against production SOC traffic
  within the constraints of this project (no real enterprise environment,
  no live analysts to generate reward signal at volume).
- Building an RL loop before the rule/graph detection pipeline and the
  approval workflow exist would mean optimizing a policy over a reward
  signal that doesn't yet reflect real detection quality — premature
  optimization of the wrong layer.

## Decision
Treat RL strictly as a **future policy-optimization layer on top of a
working deterministic baseline**, not as a first-class MVP deliverable:

1. **Stage 0 (shipped)**: `response_policy` uses a deterministic
   rule/lookup table (`PLAYBOOKS` keyed by likely objective + risk
   score threshold) as the baseline policy. This is auditable,
   explainable to analysts, and safe by construction (dry-run default,
   disruptive actions gated by `approval`).
2. **Stage 1 (near-term)**: capture analyst feedback
   (`case_management`'s `/api/v1/cases/{id}/feedback`, verdict:
   true_positive/false_positive/benign) and approval outcomes
   (`approval`'s decision + rationale) as the labeled dataset for offline
   evaluation. Every recommendation and its eventual human disposition is
   already captured in `audit` by construction (ADR 0002), so this data
   accumulates automatically from normal operation — no separate
   instrumentation project required.
3. **Stage 2**: evaluate an **offline contextual bandit** (or offline RL
   with importance-weighted/doubly-robust estimators) against the logged
   analyst-feedback dataset, using simulated counterfactual outcomes
   rather than a live environment. State: risk score, asset criticality,
   attacker stage estimate, prior actions, analyst workload. Actions:
   the same fixed `ActionClass` taxonomy already defined in
   `packages/common/aegis_common/schema/events.py`. Reward: a weighted
   combination of (stopped-attack proxy, analyst time saved, false
   positive penalty, business disruption penalty) computed from the
   logged data, never from live exploration.
4. **Stage 3 (only if time/data allow)**: PPO or DQN, still evaluated
   exclusively in simulation against replayed historical scenarios
   (`data/scenarios/`), never deployed to make live decisions
   autonomously. Any learned policy's *recommendations* still flow
   through the same `approval` gate as the deterministic baseline — RL
   changes what gets recommended, never removes the human-in-the-loop
   requirement.

## Consequences
- The MVP ships with a fully functional, if simple, response policy from
  day one; RL is additive and can be dropped without breaking the
  platform.
- Offline evaluation means the project needs a reasonably sized labeled
  feedback corpus before Stage 2 is meaningful — until then, the
  deterministic baseline is the correct comparison point in
  `docs/EVALUATION.md`'s baseline table ("Rule + heuristics" row).
- No online RL means the platform cannot "self-improve" its response
  policy in real time without a human retraining/redeploying step — an
  intentional trade-off for safety and auditability over adaptivity.

## Alternatives considered
- **Online RL from day one**: rejected — unacceptable safety risk for a
  system that can recommend disruptive containment actions, and there is
  no safe live environment to explore in.
- **Skip RL entirely**: considered reasonable and low-risk, but offline
  evaluation is cheap once feedback data exists and is called out
  explicitly in the original project brief as a desired experimentation
  track, so it's kept as an optional Stage 2/3 rather than removed.
