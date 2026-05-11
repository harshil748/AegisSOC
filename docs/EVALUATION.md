# AegisSOC Evaluation Guide

This document defines the metrics AegisSOC is evaluated against and how
to run the evaluation scripts locally. It operationalizes the
"Evaluation plan" section of `prompt.md` and is the reference for
interpreting `aegis_*` Prometheus metrics and Grafana dashboards in
`infra/grafana/dashboards/`.

## Metric definitions

### Detection metrics
| Metric | Definition | Computed from |
|---|---|---|
| Precision | TP / (TP + FP) at a chosen score threshold | Analyst feedback verdicts (`case_management` `/api/v1/cases/{id}/feedback`) vs. `Alert.risk.ensemble_score` |
| Recall | TP / (TP + FN) | Same, against a labeled scenario set (`data/scenarios/`) with known ground truth |
| F1 | Harmonic mean of precision/recall | Derived |
| False Positive Rate | FP / (FP + TN) | Same feedback corpus |
| PR-AUC / ROC-AUC | Area under precision-recall / ROC curve across score thresholds | `Alert.risk.ensemble_score` vs. labeled verdict, swept over thresholds |
| Top-k alert prioritization utility | Fraction of true positives found in the top-k ranked alerts by score | Rank alerts by `ensemble_score`, compare to labeled set |
| Attack-path / next-step prediction accuracy | Fraction of held-out attack-chain steps correctly predicted as "likely next" given prior steps | Graph model output vs. scenario ground-truth chain (`data/scenarios/*.jsonl`) |

### SOC workflow metrics
| Metric | Definition | Computed from |
|---|---|---|
| Mean time to triage (MTTT) | `case.updated_at` (first analyst action) − `case.created_at` | `cases` table timestamps |
| Analyst actions saved | Estimated actions avoided when an LLM-generated report/query is accepted vs. manual investigation baseline | Analyst feedback + report acceptance rate |
| Escalation precision | Fraction of `escalate`d cases later confirmed true positive | Feedback verdicts on escalated cases |
| Case deduplication quality | Fraction of alerts correctly clustered into an existing case vs. spuriously creating a duplicate | Manual audit of `alert_ids` clustering against ground truth |
| Time from alert to recommended action | `Action.created_at` − `Alert.created_at` | `aegis_response_recommendations_total` + timestamps |

### LLM quality metrics
| Metric | Definition | Computed from |
|---|---|---|
| Groundedness / citation rate | `len(evidence_cited) / len(claims)` — fraction of report claims tied to a cited evidence_id | `TriageReport.groundedness_score`, aggregated via `aegis_llm_reports_total` and manual claim audits |
| Hallucination rate | Fraction of reports with ≥1 entry in `unsupported_claims` after validation | `TriageReport.unsupported_claims` |
| Report completeness | Fraction of required `TriageReport` fields populated with non-trivial content | Schema-level check across a sample of reports |
| ATT&CK mapping correctness | Fraction of `attack_mapping` technique IDs that match human-labeled ground truth for the scenario | Compare to `data/scenarios/*` labels |
| Analyst-rated usefulness | 1-5 analyst rating of report usefulness (survey/UI widget) | Feedback capture (extend `case_feedback` table with a report_id + rating column) |

### System metrics
| Metric | Definition | Computed from |
|---|---|---|
| Event throughput | Events/sec accepted at ingestion | `aegis_ingestion_events_total` rate |
| Queue lag | Consumer lag per topic/consumer-group | `aegis_graph_builder_consumer_lag` (MVP proxy); production should read Kafka's own `ConsumerLag` metric per group |
| End-to-end latency (ingest→enriched) | Timestamp delta between `Provenance.ingested_at` and `enrichment.enriched_at` | Event-level timestamps carried through the pipeline |
| Graph update latency | Time from enriched event to Neo4j write completion | `aegis_graph_write_latency_seconds` histogram |
| LLM latency and cost per investigated alert | Wall-clock time + `LLM_TOKENS` \* per-token price | `aegis_llm_latency_seconds`, `aegis_llm_tokens_total` |

### Baselines
Compare every detection-quality metric across these five configurations,
in increasing sophistication, per `prompt.md`:

1. **Rule-only** — `detection`'s Sigma-like rules alone (`rule_score`).
2. **Rule + heuristics** — add asset-criticality/source-confidence weighting.
3. **Rule + feature ML** — add an XGBoost/LightGBM baseline on engineered graph features.
4. **Rule + graph ML** — add GraphSAGE/GAT/temporal-GNN scoring (`graph_score`).
5. **Rule + graph ML + LLM reasoning** — full pipeline; LLM affects only
   report quality/workflow metrics, never `ensemble_score` (per ADR 0002),
   so this baseline is compared on SOC-workflow and LLM-quality metrics,
   not detection precision/recall (which are identical to #4 by design).

## Running the evaluation scripts

All evaluation scripts live in `scripts/` and only depend on
`scripts/requirements.txt` (`pyyaml`, `requests`) — they do not require
the full backend stack to be running for the rule-level checks, and
degrade gracefully (dry-run / simulated output) when it is not.

```bash
pip install -r scripts/requirements.txt

# 1. (Re)generate the synthetic benign background corpus, if needed
python scripts/generate_samples.py --out-dir data/samples --seed 1337

# 2. Bring the stack up and seed the three canonical demo scenarios
make up
make seed          # wraps: python scripts/seed_demo.py --api-url http://localhost:8080

# ...or replay an individual scenario with realistic pacing:
python scripts/replay_scenario.py data/scenarios/phishing_ransomware_chain.json --speed 200

# 3. Score the Sigma-like rules in data/sigma/ against scenario ground truth
#    (precision/recall/F1 on expected_techniques + is_attack, optional FP
#    rate against the benign data/samples/ corpus)
python scripts/evaluate_detection.py --include-samples

# 4. Score LLM triage report groundedness against exported reports
#    (evidence_validity_rate, claim_support_ratio, ATT&CK mapping
#    precision/recall, groundedness_score_delta) — see the script's
#    docstring for the expected {scenario_id, report, evidence_pool}
#    export format once llm_triage exports reports for offline scoring.
python scripts/evaluate_llm_groundedness.py --reports-dir eval/reports/

# 5. Load-test the ingestion path directly (see "Load testing" below)
python scripts/load_test_ingest.py --rate 500 --duration 30 --api-url http://localhost:8080
```

Ground truth for detection/LLM scoring comes from each scenario's
metadata fields in `data/scenarios/*.json`: `is_attack`,
`expected_severity`, `expected_min_risk`, and `expected_techniques`
(ATT&CK IDs). `scripts/evaluate_detection.py` and
`scripts/evaluate_llm_groundedness.py` compare pipeline/LLM output
against these fields directly — see each script's module docstring for
the exact metric definitions it computes (they correspond 1:1 with the
"Detection metrics" and "LLM quality metrics" tables above).

SOC workflow metrics (MTTT, escalation precision, case-dedup quality)
require querying `case_management`/`audit` over a longer operating
window than a single scenario replay provides; compute them from the
`cases`/`case_feedback`/`audit_log` tables directly (or via
`GET /api/v1/cases`, `GET /api/v1/audit` through the gateway) once enough real
or replayed history has accumulated — no dedicated script ships for this
yet, as it needs a meaningful volume of analyst feedback to be
meaningful.

## Load testing (system metrics)

```bash
make load-test    # wraps: python scripts/load_test_ingest.py --rate 500 --duration 30
```

`scripts/load_test_ingest.py` draws events from the `data/samples/*.jsonl`
corpus (round-robin across sources) and fires them at the ingestion API
from a thread pool, reporting throughput, latency percentiles, and error
rate; it falls back to a local-only generation-rate benchmark if no
ingestion API is reachable. `tests/load/locustfile.py` is provided as an
alternative, heavier-weight Locust-based profile (including a
`GatewayUser` class exercising analyst-facing read endpoints under
concurrent load) for teams that prefer Locust's distributed/web-UI
workflow:

```bash
locust -f tests/load/locustfile.py --headless -u 200 -r 20 -t 5m --host http://localhost:8001
```

Record p50/p95/p99 latency and max sustained events/sec per run in
`eval/load_test_history.md` (create on first run) so throughput
regressions are visible over time.

## Interpreting results
- Treat baseline #1 (rule-only) as the floor — every added layer should
  improve recall and/or top-k utility without collapsing precision.
- A rising hallucination rate or falling groundedness score should block
  a release even if detection metrics are unchanged — the LLM layer's
  entire value proposition depends on trustworthy summaries (ADR 0004).
- Compare MTTT and escalation precision before/after enabling
  `llm_triage` to quantify the actual analyst-time benefit the copilot
  provides (the core claim this project is meant to demonstrate).
