#!/usr/bin/env python3
"""Score LLM triage report groundedness: evidence citation validity, claim
support ratio, and ATT&CK mapping correctness against scenario ground truth.

The core principle in this project is that the LLM must never be the primary
detector and must never assert claims that are not backed by retrieved
evidence (see prompt.md / TriageReport schema in
packages/common/aegis_common/schema/events.py). This script operationalizes
that check:

  - evidence_validity_rate: fraction of `evidence_cited` IDs that actually
    exist in the case's real evidence pool (catches fabricated citations).
  - claim_support_ratio: evidence_cited / (evidence_cited + unsupported_claims),
    i.e. how much of the narrative is grounded vs. self-flagged unsupported.
  - technique_mapping precision/recall: attack_mapping technique_ids vs the
    scenario's expected_techniques ground truth.
  - groundedness_score_delta: self-reported groundedness_score vs. the
    computed evidence_validity_rate (large negative deltas mean the model is
    overconfident about its own groundedness).

Because services/llm_triage does not emit real reports yet, this script ships
with built-in example TriageReport fixtures (one well-grounded, one with a
deliberately injected hallucinated citation + unsupported claim, one for the
benign false-positive scenario) so it is runnable standalone. Point it at a
directory of real exported reports once the triage service exists.

Usage:
    python scripts/evaluate_llm_groundedness.py
    python scripts/evaluate_llm_groundedness.py --reports-dir path/to/exported_reports
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"


def build_evidence_pool(scenario: dict) -> dict[str, dict]:
    pool = {}
    for i, event in enumerate(scenario["events"]):
        eid = f"{scenario['scenario_id']}-evt-{i:03d}"
        pool[eid] = {
            "kind": "event",
            "source": event.get("source"),
            "timestamp": event.get("timestamp"),
        }
    return pool


def builtin_fixture_reports(scenarios_by_id: dict[str, dict]) -> list[dict]:
    """Illustrative TriageReport-shaped fixtures. `evidence_cited` values are
    evidence IDs from build_evidence_pool(); one is deliberately fabricated
    to demonstrate hallucination detection."""

    reports = []

    if "phishing_ransomware_chain" in scenarios_by_id:
        reports.append({
            "scenario_id": "phishing_ransomware_chain",
            "report": {
                "report_id": "fixture-report-001",
                "case_id": "CASE-DEMO-001",
                "summary": (
                    "Elena Martinez (WKSTN-1147) opened a macro-enabled invoice attachment "
                    "delivered from a spoofed domain (SPF/DMARC fail). This spawned an "
                    "encoded PowerShell stager that fetched a second-stage payload, dumped "
                    "LSASS via comsvcs.dll, and reused a harvested domain-admin credential "
                    "to move laterally via PsExec/WMI to SRV-FILE01 and SRV-SQL01, culminating "
                    "in ransomware encrypting the Finance share with the .aegislock extension."
                ),
                "likely_objective": "Financially motivated ransomware deployment via credential-enabled lateral movement.",
                "attack_mapping": [
                    {"technique_id": "T1566.001", "rationale": "Spearphishing attachment with macro-enabled document."},
                    {"technique_id": "T1204.002", "rationale": "User execution of the malicious attachment."},
                    {"technique_id": "T1059.001", "rationale": "Encoded PowerShell stager spawned from WINWORD.EXE."},
                    {"technique_id": "T1003.001", "rationale": "LSASS memory dump via comsvcs.dll MiniDump."},
                    {"technique_id": "T1021.002", "rationale": "PsExec-style SMB/admin-share lateral movement to SRV-FILE01."},
                    {"technique_id": "T1486", "rationale": "Mass file encryption with the .aegislock extension on Finance share."},
                ],
                "investigation_queries": [
                    "List all hosts that resolved secure-office365-update.com or cdn-office-update-cache.net in the last 30 days.",
                    "Enumerate all logons by jtorres across the environment in the incident window.",
                ],
                "containment_recommendation": "Isolate WKSTN-1147, SRV-FILE01, and SRV-SQL01; force-reset the jtorres credential; block the two C2 domains/IPs at the perimeter.",
                "confidence_explanation": "High confidence: every stage of the kill chain has direct, timestamped telemetry with consistent host/user/IOC linkage.",
                "groundedness_score": 0.95,
                "evidence_cited": [
                    "phishing_ransomware_chain-evt-000",
                    "phishing_ransomware_chain-evt-002",
                    "phishing_ransomware_chain-evt-003",
                    "phishing_ransomware_chain-evt-006",
                    "phishing_ransomware_chain-evt-010",
                    "phishing_ransomware_chain-evt-015",
                    "phishing_ransomware_chain-evt-016",
                ],
                "unsupported_claims": [],
                "model_id": "gpt-4o-mini",
            },
        })

    if "repeat_attacker_infra" in scenarios_by_id:
        reports.append({
            "scenario_id": "repeat_attacker_infra",
            "report": {
                "report_id": "fixture-report-002",
                "case_id": "CASE-DEMO-002",
                "summary": (
                    "A trojanized 'CloudSync Agent' installer led kbrooks's host (WKSTN-1298) "
                    "to beacon to api.cloudsync-telemetry.com, infrastructure previously seen "
                    "46 days earlier in incident INC-2026-0603 against a different host/user."
                ),
                "likely_objective": "Re-establishing C2 access using previously-seized infrastructure, possibly the same operator.",
                "attack_mapping": [
                    {"technique_id": "T1566.001", "rationale": "Phishing email delivering a trojanized installer."},
                    {"technique_id": "T1204.002", "rationale": "User executed the CloudSyncAgentSetup.exe installer."},
                    {"technique_id": "T1071.001", "rationale": "TLS beacon to the same C2 domain observed in the prior incident."},
                    # Deliberately unsupported/fabricated claim below, with a citation
                    # to an evidence ID that does not exist in the case's evidence pool.
                    {"technique_id": "T1552.001", "rationale": "Attacker exfiltrated credentials stored in a browser password vault."},
                ],
                "investigation_queries": [
                    "Pull all DNS answers for api.cloudsync-telemetry.com over the last 90 days across all sinkhole/passive DNS sources.",
                ],
                "containment_recommendation": "Isolate WKSTN-1298, block the domain and both observed IPs, and re-scope INC-2026-0603 as a linked/reopened incident.",
                "confidence_explanation": "Moderate-high confidence based on shared C2 domain and sibling-netblock IP reuse across two time-separated waves.",
                "groundedness_score": 0.9,
                "evidence_cited": [
                    "repeat_attacker_infra-evt-005",
                    "repeat_attacker_infra-evt-006",
                    "repeat_attacker_infra-evt-007",
                    "repeat_attacker_infra-evt-999",  # fabricated - not in the real evidence pool
                ],
                "unsupported_claims": [
                    "Attacker exfiltrated credentials stored in a browser password vault.",
                ],
                "model_id": "gpt-4o-mini",
            },
        })

    if "benign_admin_false_positive" in scenarios_by_id:
        reports.append({
            "scenario_id": "benign_admin_false_positive",
            "report": {
                "report_id": "fixture-report-003",
                "case_id": "CASE-DEMO-003",
                "summary": (
                    "A Base64-encoded PowerShell invocation on WKSTN-1188 superficially matches "
                    "encoded-command detection logic, but originates from a Microsoft-signed SCCM "
                    "client script launched by Task Scheduler under the svc-sccm service account, "
                    "targeting only internal SCCM infrastructure. No credential access or lateral "
                    "movement follows."
                ),
                "likely_objective": "None -- routine, change-managed patch-compliance automation.",
                "attack_mapping": [
                    {"technique_id": "T1059.001", "rationale": "Encoded PowerShell command line matched the detection pattern, but context indicates benign automation."},
                ],
                "investigation_queries": [
                    "Confirm svc-sccm's historical execution pattern matches this month's scheduled run.",
                ],
                "containment_recommendation": "No action required; close as false positive and tune the rule to exclude signed SCCM client scripts on Task Scheduler parentage.",
                "confidence_explanation": "High confidence this is benign: signed binary, known service account, internal-only destination, no follow-on credential access or lateral movement.",
                "groundedness_score": 0.92,
                "evidence_cited": [
                    "benign_admin_false_positive-evt-001",
                    "benign_admin_false_positive-evt-002",
                    "benign_admin_false_positive-evt-003",
                    "benign_admin_false_positive-evt-004",
                ],
                "unsupported_claims": [],
                "model_id": "gpt-4o-mini",
            },
        })

    return reports


def load_reports_dir(reports_dir: Path) -> list[dict]:
    reports = []
    for path in sorted(reports_dir.glob("*.json")):
        doc = json.loads(path.read_text())
        reports.append(doc)
    return reports


def score_report(entry: dict, scenarios_by_id: dict[str, dict]) -> dict:
    scenario_id = entry.get("scenario_id")
    report = entry["report"]
    scenario = scenarios_by_id.get(scenario_id)
    evidence_pool = build_evidence_pool(scenario) if scenario else entry.get("evidence_pool", {})

    cited = report.get("evidence_cited", [])
    unsupported = report.get("unsupported_claims", [])

    valid_citations = [c for c in cited if c in evidence_pool]
    hallucinated_citations = [c for c in cited if c not in evidence_pool]
    evidence_validity_rate = (len(valid_citations) / len(cited)) if cited else 1.0

    total_claims = len(cited) + len(unsupported)
    claim_support_ratio = (len(cited) / total_claims) if total_claims else 1.0

    predicted_techniques = {m.get("technique_id") for m in report.get("attack_mapping", []) if m.get("technique_id")}
    expected_techniques = set(scenario.get("expected_techniques", [])) if scenario else set()
    if expected_techniques:
        tp = len(predicted_techniques & expected_techniques)
        mapping_precision = tp / len(predicted_techniques) if predicted_techniques else 0.0
        mapping_recall = tp / len(expected_techniques) if expected_techniques else 0.0
    else:
        mapping_precision = mapping_recall = None

    self_reported = report.get("groundedness_score", None)
    computed_groundedness = round((evidence_validity_rate + claim_support_ratio) / 2, 3)
    delta = round(self_reported - computed_groundedness, 3) if self_reported is not None else None

    return {
        "report_id": report.get("report_id"),
        "scenario_id": scenario_id,
        "evidence_cited": len(cited),
        "hallucinated_citations": hallucinated_citations,
        "evidence_validity_rate": round(evidence_validity_rate, 3),
        "unsupported_claims": len(unsupported),
        "claim_support_ratio": round(claim_support_ratio, 3),
        "mapping_precision": round(mapping_precision, 3) if mapping_precision is not None else None,
        "mapping_recall": round(mapping_recall, 3) if mapping_recall is not None else None,
        "self_reported_groundedness": self_reported,
        "computed_groundedness": computed_groundedness,
        "groundedness_delta": delta,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reports-dir", default=None, help="directory of exported {scenario_id, report[, evidence_pool]} JSON files")
    parser.add_argument("--scenarios-dir", default=str(SCENARIOS_DIR))
    args = parser.parse_args()

    scenarios_by_id = {}
    for path in sorted(Path(args.scenarios_dir).glob("*.json")):
        doc = json.loads(path.read_text())
        scenarios_by_id[doc["scenario_id"]] = doc

    if args.reports_dir:
        entries = load_reports_dir(Path(args.reports_dir))
        print(f"Loaded {len(entries)} real triage reports from {args.reports_dir}\n")
    else:
        entries = builtin_fixture_reports(scenarios_by_id)
        print(f"No --reports-dir given; using {len(entries)} built-in example TriageReport fixtures "
              "(one includes a deliberately injected hallucinated citation to demonstrate detection).\n")

    results = [score_report(e, scenarios_by_id) for e in entries]

    for r in results:
        print(f"=== {r['report_id']} ({r['scenario_id']}) ===")
        print(f"  evidence_cited={r['evidence_cited']}  evidence_validity_rate={r['evidence_validity_rate']:.2f}"
              + (f"  HALLUCINATED={r['hallucinated_citations']}" if r["hallucinated_citations"] else ""))
        print(f"  unsupported_claims={r['unsupported_claims']}  claim_support_ratio={r['claim_support_ratio']:.2f}")
        if r["mapping_precision"] is not None:
            print(f"  ATT&CK mapping precision={r['mapping_precision']:.2f}  recall={r['mapping_recall']:.2f}")
        print(f"  self_reported_groundedness={r['self_reported_groundedness']}  computed={r['computed_groundedness']}  "
              f"delta={r['groundedness_delta']}")
        print()

    if results:
        n = len(results)
        print("=== Aggregate ===")
        print(f"  reports scored: {n}")
        print(f"  mean evidence_validity_rate: {sum(r['evidence_validity_rate'] for r in results) / n:.3f}")
        print(f"  mean claim_support_ratio:    {sum(r['claim_support_ratio'] for r in results) / n:.3f}")
        mapped = [r for r in results if r["mapping_precision"] is not None]
        if mapped:
            print(f"  mean ATT&CK mapping precision: {sum(r['mapping_precision'] for r in mapped) / len(mapped):.3f}")
            print(f"  mean ATT&CK mapping recall:    {sum(r['mapping_recall'] for r in mapped) / len(mapped):.3f}")
        hallucinating_reports = [r for r in results if r["hallucinated_citations"]]
        print(f"  reports with >=1 hallucinated citation: {len(hallucinating_reports)}/{n}")


if __name__ == "__main__":
    main()
