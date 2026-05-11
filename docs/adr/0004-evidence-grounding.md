# ADR 0004: Evidence Grounding and Provenance Prevent Hallucinated Triage

## Status
Accepted

## Context
Given ADR 0002 (LLM is not the primary detector), the LLM's remaining
job — summarizing evidence, mapping to ATT&CK, drafting reports,
justifying recommendations — is still high-stakes: an analyst reading a
triage report will reasonably trust it unless given a reason not to.
An LLM that "sounds confident" while inventing a detail (a technique
that wasn't observed, an IP that isn't actually in the evidence) causes
exactly the alert-fatigue-by-a-different-name problem the platform is
meant to solve, and is worse than no summary at all because it's
plausible.

Two failure modes must be prevented:
1. **Hallucination**: the model asserts something not supported by any
   retrieved evidence item.
2. **Unbounded context**: dumping arbitrarily large amounts of raw event
   data into the prompt does not reliably improve output quality and
   can actively mislead the model (per the research guidance in
   `prompt.md`), while also increasing cost/latency and prompt-injection
   surface area (untrusted text is more likely to be present as context
   grows).

## Decision
Every LLM-produced artifact must be **traceable back to specific
evidence objects**, and evidence is **retrieved and bounded, not
dumped**:

- `EvidenceItem` (`packages/common/aegis_common/schema/events.py`) is
  the atomic unit passed into a prompt: `evidence_id`, `kind`
  (event/node/edge/detection/intel), `summary`, `source`, `payload`.
  Every such item carries a pointer back to its raw source
  (`Provenance.raw_event_id`/`topic`/`offset` or a graph
  node/edge/detection ID) so an analyst — or an automated audit — can
  always answer "where did this claim come from?".
- Evidence retrieval for a `TriageRequest` is **capped** at
  `llm_max_evidence_items` (default 40, configurable via
  `LLM_MAX_EVIDENCE_ITEMS`) — a deliberately small, curated set chosen by
  relevance (same entity/case, most recent, highest detection score)
  rather than an unbounded window, directly implementing the "more
  context is not always better" guidance.
- The `llm_triage` service sanitizes evidence text for prompt-injection
  markers *before* it enters the prompt (see
  `docs/threat-model/THREAT_MODEL.md`), because untrusted evidence text
  (email bodies, DNS names, intel notes) is exactly the channel an
  attacker could otherwise use to manipulate the model.
- Every generated `TriageReport` carries:
  - `evidence_cited`: the evidence_ids the summary is actually grounded
    in,
  - `unsupported_claims`: any claim the output-validation step could not
    tie back to `evidence_cited` (stripped before the report reaches an
    analyst, but the fact that stripping occurred is preserved for audit
    and eval),
  - `groundedness_score`: a proxy metric (fraction of claims with a
    citation) tracked over time in `docs/EVALUATION.md`.
- The LLM is instructed to store **concise rationale**, not raw
  chain-of-thought, in any persisted artifact — hidden reasoning traces
  are not treated as auditable evidence and are not stored.
- Every triage call, its evidence set (or a hash of it), and its output
  are written to `audit` (`prompt_hash`, `evidence_refs`) — this is the
  mechanism that makes "did the LLM ever see this attacker's data
  before recommending X" answerable after the fact.

## Consequences
- Building an evidence-retrieval step (rather than "pass the whole case")
  is extra engineering work, but it's what makes the LLM's output
  reviewable and is a prerequisite for the groundedness eval metric.
- A capped evidence window means very large/complex cases may get a
  summary based on a subset of evidence; the UI must make it clear which
  evidence was actually used (`evidence_cited`) so an analyst knows to
  dig deeper for anything not covered.
- Output validation (stripping unsupported claims) is a soft control —
  it reduces but does not guarantee zero hallucination; groundedness is
  therefore tracked as a first-class eval metric, not assumed.

## Alternatives considered
- **Trust the model's citations without validation**: rejected — the
  validation step exists specifically because models cite incorrectly
  or fabricate under pressure to appear complete.
- **No evidence cap ("send everything")**: rejected per the research
  guidance and the cost/latency/injection-surface reasons above.
- **Require human review of every citation before display**: rejected
  as an MVP requirement (too slow for triage-time usage) but noted as a
  reasonable addition for high-severity cases in `docs/SECURITY.md`.
