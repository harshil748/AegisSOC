# ADR 0002: The LLM Is Never the Primary Detector

## Status
Accepted

## Context
It is tempting to point an LLM at raw logs and ask "is this malicious?".
This is attractive because it requires no feature engineering or
labeled training data, but it is unsuitable as a primary detection
mechanism for a SOC platform:

- LLMs are **non-deterministic and unauditable** as classifiers — the
  same input can yield different outputs across calls/model versions,
  which is unacceptable for a control that gates security decisions.
- LLMs are **vulnerable to prompt injection** from the exact untrusted
  inputs they'd be classifying (email bodies, DNS names, process command
  lines, threat-intel notes) — see
  `docs/threat-model/THREAT_MODEL.md`.
- LLMs **hallucinate** — they can assert a technique or IOC that isn't
  actually present in the evidence, which is far more dangerous in a
  detector than in an assistant, because a detector's output directly
  drives escalation/containment.
- LLM inference is **comparatively expensive and slow** relative to
  rule/graph scoring, and 100M logs/day cannot economically or
  latency-wise run through an LLM per event.
- Research on LLM-assisted SOC workflows consistently finds LLMs more
  reliable as **evidence-guided decision-support systems** than as
  standalone classifiers, and that giving a model excessive raw context
  can *reduce* triage quality rather than improve it.

## Decision
Detection is produced entirely by deterministic and statistical
components that never call an LLM:

1. **Rule-based detections** (Sigma-like predicate rules in the
   `detection` service, see `data/sigma/`) — cheap, explainable, auditable.
2. **Correlation** across multiple events/entities for multi-step
   patterns.
3. **Graph feature extraction** (fan-in/out, path novelty, technique
   co-occurrence) computed from the Neo4j graph built by
   `graph_builder`.
4. **Graph/sequence model scoring** (GraphSAGE/GAT/temporal-GNN, or
   XGBoost/LightGBM baselines) trained offline on labeled outcomes.
5. A **calibrated ensemble** (`RiskScores` in
   `packages/common/aegis_common/schema/events.py`) combining rule,
   heuristic, graph, and intel-confidence signals into one score that
   determines whether an `Alert`/`Case` is created and how it's
   prioritized.

The LLM (`llm_triage` service) is invoked **only after** an alert/case
already exists from the pipeline above. Its role is strictly:
summarization, ATT&CK mapping of *already-detected* techniques,
investigation-query generation, report drafting, and response
justification — all grounded in a bounded, retrieved evidence set (see
ADR 0004). The LLM **cannot**:
- set or override `risk.ensemble_score` / `risk.calibrated_score`,
- create or close an `Alert`/`Case` on its own,
- invent evidence not present in `evidence_cited`,
- execute any action (see ADR on approval workflow / `approval` service).

This boundary is enforced structurally, not just by policy: `llm_triage`
has no write access to the detection scoring path or Neo4j, and every
`TriageReport` is validated for `unsupported_claims` before being shown
to an analyst.

## Consequences
- Detection quality is bounded by the rule/graph/ML pipeline's own
  recall — the LLM cannot "catch" something the pipeline entirely
  missed. This is intentional: false negatives from a deterministic
  pipeline are debuggable and improvable (add a rule, retrain a model);
  false negatives papered over by an LLM guess would not be.
- More engineering investment goes into Sigma rules, graph feature
  design, and model calibration than into prompt engineering — matches
  the project's stated core principle and the internship-MVP guidance to
  build the rule/graph pipeline before layering on LLM reasoning.
- The LLM still adds real value: it is dramatically better than either
  rules or graph models at turning a cluster of raw evidence into a
  readable analyst narrative, and at generating good follow-up
  investigation queries — so it's used for exactly that.

## Alternatives considered
- **LLM-as-classifier on raw events**: rejected for cost, latency,
  auditability, and prompt-injection exposure reasons above.
- **LLM-as-reranker of rule/graph outputs**: partially adopted — the
  ensemble score already does calibrated reranking without an LLM;
  revisit an LLM reranker only if the ensemble proves insufficient and
  only with strict evidence grounding.
- **No LLM at all**: rejected — evidence-grounded summarization and
  investigation planning measurably reduce analyst triage time (see
  `docs/EVALUATION.md` SOC workflow metrics), which is the core value
  proposition of the platform.
