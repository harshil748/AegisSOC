#!/usr/bin/env python3
"""Score Sigma-like rules in data/sigma/ against scenario ground truth.

Loads every scenario in data/scenarios/*.json, runs the mini rule engine over
each scenario's raw events, and compares the set of ATT&CK technique IDs the
rules fired against `expected_techniques` (and whether *any* rule fired
against `is_attack`). Reports per-scenario and aggregate precision/recall/F1
plus a confusion-style summary, and can optionally run the same rules over
the benign background corpus in data/samples/ to estimate a false-positive
rate on "normal" traffic.

Usage:
    python scripts/evaluate_detection.py
    python scripts/evaluate_detection.py --include-samples
    python scripts/evaluate_detection.py --rules-dir data/sigma --scenarios-dir data/scenarios
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required: pip install pyyaml (see scripts/requirements.txt)"
    ) from exc


# --------------------------------------------------------------------------
# Event flattening: map heterogeneous raw vendor payloads onto a common,
# source-agnostic field vocabulary that Sigma selections match against.
# --------------------------------------------------------------------------

def _hash_from_sysmon(hashes_field: str | None) -> str | None:
    if not hashes_field:
        return None
    for part in hashes_field.split(","):
        if part.upper().startswith("SHA256="):
            return part.split("=", 1)[1]
    return None


def flatten_event(event: dict) -> dict[str, Any]:
    source = event.get("source", "unknown")
    raw = event.get("raw", event.get("event", {})) or {}
    flat: dict[str, Any] = {"source": source, "timestamp": event.get("timestamp")}

    if source == "sysmon":
        flat.update({
            "event_id": raw.get("EventID"),
            "host": (raw.get("Computer") or raw.get("host") or "").split(".")[0] or None,
            "user": raw.get("User") or raw.get("user"),
            "image": raw.get("Image"),
            "command_line": raw.get("CommandLine"),
            "parent_image": raw.get("ParentImage"),
            "parent_command_line": raw.get("ParentCommandLine"),
            "target_filename": raw.get("TargetFilename"),
            "target_object": raw.get("TargetObject"),
            "dest_ip": raw.get("DestinationIp"),
            "dest_port": raw.get("DestinationPort"),
            "dest_hostname": raw.get("DestinationHostname"),
            "sha256": _hash_from_sysmon(raw.get("Hashes")),
            "integrity_level": raw.get("IntegrityLevel"),
        })
    elif source == "edr":
        net = raw.get("network_connections", []) or []
        flat.update({
            "host": raw.get("host"),
            "user": raw.get("user"),
            "image": raw.get("process_name"),
            "command_line": raw.get("command_line"),
            "parent_image": raw.get("parent_process"),
            "sha256": raw.get("sha256"),
            "signed": raw.get("signed"),
            "reputation": raw.get("reputation"),
            "mitre_techniques": raw.get("mitre_techniques", []),
            "dest_ip": [c.get("dst_ip") for c in net] or None,
        })
    elif source in ("ad_auth", "active_directory"):
        flat.update({
            "event_id": raw.get("EventID"),
            "host": raw.get("WorkstationName") or (raw.get("Computer") or "").split(".")[0] or None,
            "user": raw.get("TargetUserName"),
            "src_ip": raw.get("IpAddress"),
            "logon_type": raw.get("LogonType"),
            "service_name": raw.get("ServiceName"),
            "privilege_list": raw.get("PrivilegeList"),
            "failure_reason": raw.get("FailureReason"),
        })
    elif source == "cloudtrail":
        identity = raw.get("userIdentity", {}) or {}
        additional = raw.get("additionalEventData", {}) or {}
        flat.update({
            "event_name": raw.get("eventName"),
            "event_source": raw.get("eventSource"),
            "user_name": identity.get("userName") or identity.get("type"),
            "user_type": identity.get("type"),
            "src_ip": raw.get("sourceIPAddress"),
            "mfa_used": additional.get("MFAUsed"),
            "error_code": raw.get("errorCode"),
            "read_only": raw.get("readOnly"),
            "aws_region": raw.get("awsRegion"),
        })
    elif source in ("kubernetes", "k8s"):
        obj_ref = raw.get("objectRef", {}) or {}
        user = raw.get("user", {}) or {}
        flat.update({
            "k8s_verb": raw.get("verb"),
            "k8s_resource": obj_ref.get("resource"),
            "k8s_namespace": obj_ref.get("namespace"),
            "user": user.get("username"),
            "src_ip": (raw.get("sourceIPs") or [None])[0],
            "response_code": (raw.get("responseStatus") or {}).get("code"),
        })
    elif source == "email":
        attachments = raw.get("attachments", []) or []
        flat.update({
            "email_from": raw.get("from"),
            "email_to": raw.get("to"),
            "subject": raw.get("subject"),
            "attachment_name": attachments[0].get("filename") if attachments else None,
            "attachment_names": [a.get("filename") for a in attachments] or None,
            "urls": raw.get("urls") or None,
            "spf": raw.get("spf"),
            "dkim": raw.get("dkim"),
            "dmarc": raw.get("dmarc"),
            "verdict": raw.get("verdict"),
        })
    elif source == "zeek":
        log_type = raw.get("log_type")
        query = raw.get("query")
        flat.update({
            "zeek_log_type": log_type,
            "src_ip": raw.get("id.orig_h"),
            "dest_ip": raw.get("id.resp_h"),
            "dest_port": raw.get("id.resp_p"),
            "dns_query": query,
            "dns_query_length": len(query) if isinstance(query, str) else None,
            "http_host": raw.get("host"),
            "http_uri": raw.get("uri"),
            "service": raw.get("service"),
        })
    elif source == "suricata":
        alert = raw.get("alert", {}) or {}
        flat.update({
            "alert_signature": alert.get("signature"),
            "alert_category": alert.get("category"),
            "src_ip": raw.get("src_ip"),
            "dest_ip": raw.get("dest_ip"),
            "dest_port": raw.get("dest_port"),
        })
    elif source in ("dns", "firewall", "firewall_dns"):
        query = raw.get("query")
        flat.update({
            "zeek_log_type": "dns" if query else None,
            "dns_query": query,
            "dns_query_length": len(query) if isinstance(query, str) else None,
            "src_ip": raw.get("client_ip") or raw.get("src_ip"),
            "dest_ip": raw.get("dst_ip") or raw.get("resolved_ip"),
            "action": raw.get("action"),
            "rule_name": raw.get("rule_name"),
        })
    return flat


# --------------------------------------------------------------------------
# Mini Sigma-like rule engine
# --------------------------------------------------------------------------

def _match_one(actual: Any, modifier: str, expected: Any) -> bool:
    if actual is None:
        return modifier == "not_exists"
    if modifier == "exists":
        return True

    expected_list = expected if isinstance(expected, list) else [expected]
    actual_list = actual if isinstance(actual, list) else [actual]

    for a in actual_list:
        for e in expected_list:
            if modifier in ("eq", "equals"):
                if isinstance(a, str) and isinstance(e, str):
                    if a.lower() == e.lower():
                        return True
                elif a == e or str(a).lower() == str(e).lower():
                    return True
            elif modifier == "contains":
                if isinstance(a, str) and isinstance(e, str) and e.lower() in a.lower():
                    return True
            elif modifier == "startswith":
                if isinstance(a, str) and isinstance(e, str) and a.lower().startswith(e.lower()):
                    return True
            elif modifier == "endswith":
                if isinstance(a, str) and isinstance(e, str) and a.lower().endswith(e.lower()):
                    return True
            elif modifier == "gt":
                try:
                    if float(a) > float(e):
                        return True
                except (TypeError, ValueError):
                    pass
            elif modifier == "lt":
                try:
                    if float(a) < float(e):
                        return True
                except (TypeError, ValueError):
                    pass
    return False


def eval_block(flat: dict, block: dict) -> bool:
    for key, expected in block.items():
        field, _, modifier = key.partition("|")
        modifier = modifier or "eq"
        if not _match_one(flat.get(field), modifier, expected):
            return False
    return True


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def eval_condition(flat: dict, blocks: dict[str, dict]) -> bool:
    condition = blocks.get("__condition__", "selection")
    known = {name: eval_block(flat, block) for name, block in blocks.items() if name != "__condition__"}
    safe_expr = condition
    for name in sorted(known, key=len, reverse=True):
        safe_expr = re.sub(rf"\b{re.escape(name)}\b", str(known[name]), safe_expr)
    tokens = set(_TOKEN_RE.findall(safe_expr))
    allowed = {"and", "or", "not", "True", "False"}
    if not tokens.issubset(allowed):
        raise ValueError(f"Unsafe/unknown token(s) in condition: {tokens - allowed}")
    node = ast.parse(safe_expr, mode="eval")
    return bool(eval(compile(node, "<condition>", "eval"), {"__builtins__": {}}, {}))


class SigmaRule:
    def __init__(self, path: Path, doc: dict):
        self.path = path
        self.id = doc.get("id", path.stem)
        self.title = doc.get("title", path.stem)
        self.level = doc.get("level", "medium")
        self.status = doc.get("status", "experimental")
        self.technique_ids = doc.get("technique_ids", [])
        detection = doc.get("detection", {})
        self.blocks = {k: v for k, v in detection.items() if k != "condition"}
        self.blocks["__condition__"] = detection.get("condition", "selection")

    def matches(self, flat_event: dict) -> bool:
        try:
            return eval_condition(flat_event, self.blocks)
        except Exception:
            return False


def load_rules(rules_dir: Path) -> list[SigmaRule]:
    rules = []
    for path in sorted(rules_dir.glob("*.yml")) + sorted(rules_dir.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        rules.append(SigmaRule(path, doc))
    return rules


def load_scenarios(scenarios_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(scenarios_dir.glob("*.json"))]


def load_samples(samples_dir: Path) -> list[dict]:
    events = []
    for path in sorted(samples_dir.glob("*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    return events


def run_rules(rules: list[SigmaRule], events: list[dict]) -> tuple[set[str], dict[str, list[dict]]]:
    """Returns (fired technique_ids, {rule_id: [matched events]})."""
    fired_techniques: set[str] = set()
    hits: dict[str, list[dict]] = {}
    for event in events:
        flat = flatten_event(event)
        for rule in rules:
            if rule.matches(flat):
                fired_techniques.update(rule.technique_ids)
                hits.setdefault(rule.id, []).append(event)
    return fired_techniques, hits


def precision_recall_f1(predicted: set[str], expected: set[str]) -> tuple[float, float, float]:
    if not predicted and not expected:
        return 1.0, 1.0, 1.0
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", default="data/sigma")
    parser.add_argument("--scenarios-dir", default="data/scenarios")
    parser.add_argument("--samples-dir", default="data/samples")
    parser.add_argument("--include-samples", action="store_true", help="also estimate FP rate on benign background corpus")
    args = parser.parse_args()

    rules = load_rules(Path(args.rules_dir))
    scenarios = load_scenarios(Path(args.scenarios_dir))

    print(f"Loaded {len(rules)} Sigma rules from {args.rules_dir}")
    print(f"Loaded {len(scenarios)} scenarios from {args.scenarios_dir}\n")

    agg_precision, agg_recall, agg_f1 = [], [], []

    for scenario in scenarios:
        events = scenario["events"]
        expected = set(scenario.get("expected_techniques", []))
        is_attack_expected = scenario.get("is_attack", True)

        predicted, hits = run_rules(rules, events)
        precision, recall, f1 = precision_recall_f1(predicted, expected)
        agg_precision.append(precision)
        agg_recall.append(recall)
        agg_f1.append(f1)

        fired_any_rule = len(hits) > 0
        note = ""
        if is_attack_expected and not fired_any_rule:
            note = "  [MISS: attack scenario triggered no rules]"
        elif not is_attack_expected and fired_any_rule:
            note = "  [expected: benign scenario superficially triggers rule(s); ensemble/graph layer should down-rank]"

        print(f"=== {scenario['scenario_id']} ==={note}")
        print(f"  expected_severity={scenario.get('expected_severity')}  is_attack={is_attack_expected}")
        print(f"  expected_techniques   ({len(expected):2d}): {sorted(expected)}")
        print(f"  detected_techniques   ({len(predicted):2d}): {sorted(predicted)}")
        print(f"  rules fired: {len(hits)} -> {sorted(hits.keys())}")
        print(f"  precision={precision:.2f}  recall={recall:.2f}  f1={f1:.2f}")
        print()

    if agg_f1:
        print("=== Aggregate across scenarios ===")
        print(f"  mean precision: {sum(agg_precision)/len(agg_precision):.3f}")
        print(f"  mean recall:    {sum(agg_recall)/len(agg_recall):.3f}")
        print(f"  mean f1:        {sum(agg_f1)/len(agg_f1):.3f}")

    if args.include_samples:
        print("\n=== Benign background corpus false-positive check ===")
        samples = load_samples(Path(args.samples_dir))
        _, hits = run_rules(rules, samples)
        total_fp = sum(len(v) for v in hits.values())
        print(f"  background events scanned: {len(samples)}")
        print(f"  rule hits on benign corpus: {total_fp} ({total_fp / max(len(samples),1) * 100:.2f}% of events)")
        for rule_id, matched in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            print(f"    {rule_id}: {len(matched)} hits")


if __name__ == "__main__":
    main()
