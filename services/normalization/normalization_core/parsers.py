"""Per-source parsers converting raw telemetry payloads into CanonicalEvent.

Each parser is intentionally defensive: unknown/missing fields degrade
gracefully rather than raising, so a single malformed record cannot ever
raise a KeyError. Genuinely unparseable records are surfaced upstream so the
caller can route them to the DLQ.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from dateutil import parser as dateparser

from aegis_common.schema.events import CanonicalEvent, Severity, TelemetrySource

# Reliability prior per source, used as the CanonicalEvent.source_confidence
# baseline before any per-record adjustment.
SOURCE_CONFIDENCE: dict[str, float] = {
    TelemetrySource.SYSMON.value: 0.9,
    TelemetrySource.WINDOWS.value: 0.85,
    TelemetrySource.ZEEK.value: 0.85,
    TelemetrySource.SURICATA.value: 0.8,
    TelemetrySource.FIREWALL.value: 0.75,
    TelemetrySource.DNS.value: 0.7,
    TelemetrySource.EDR.value: 0.9,
    TelemetrySource.ACTIVE_DIRECTORY.value: 0.95,
    TelemetrySource.CLOUDTRAIL.value: 0.9,
    TelemetrySource.KUBERNETES.value: 0.85,
    TelemetrySource.EMAIL.value: 0.6,
    TelemetrySource.THREAT_INTEL.value: 0.95,
    TelemetrySource.SYNTHETIC.value: 0.5,
}

SYSMON_EVENT_TYPES = {
    1: "process_create",
    3: "network_connection",
    5: "process_terminate",
    7: "image_load",
    8: "create_remote_thread",
    10: "process_access",
    11: "file_create",
    12: "registry_event",
    13: "registry_event",
    22: "dns_query",
    23: "file_delete",
}

AD_EVENT_TYPES = {
    4624: "logon",
    4625: "logon_failure",
    4672: "special_privileges_assigned",
    4688: "process_create",
    4720: "account_created",
    4728: "group_membership_change",
}


def normalize_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = dateparser.parse(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _strip_domain_user(value: str | None) -> str | None:
    if not value:
        return value
    return value.split("\\")[-1].lower()


def parse_sysmon(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    event_id_num = int(payload.get("EventID", 0) or 0)
    event_type = SYSMON_EVENT_TYPES.get(event_id_num, f"sysmon_event_{event_id_num}")
    severity = Severity.INFORMATIONAL
    if event_type in {"process_access", "create_remote_thread"}:
        severity = Severity.MEDIUM

    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.SYSMON,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.SYSMON.value],
        event_type=event_type,
        severity=severity,
        host=payload.get("Computer"),
        user=_strip_domain_user(payload.get("User")),
        process=payload.get("Image"),
        process_id=payload.get("ProcessId"),
        parent_process=payload.get("ParentImage") or payload.get("SourceImage"),
        parent_process_id=payload.get("ParentProcessId") or payload.get("SourceProcessId"),
        command_line=payload.get("CommandLine"),
        file_path=payload.get("TargetFilename"),
        file_hash=(payload.get("Hashes") or "").replace("SHA256=", "") or None,
        registry_key=payload.get("TargetObject"),
        domain=payload.get("QueryName"),
        raw=payload,
    )


def parse_zeek(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    log_type = payload.get("log_type", "conn")
    if log_type == "dns":
        answers = payload.get("answers") or []
        return CanonicalEvent(
            tenant_id=tenant_id,
            timestamp=timestamp,
            source=TelemetrySource.ZEEK,
            source_confidence=SOURCE_CONFIDENCE[TelemetrySource.ZEEK.value],
            event_type="zeek_dns",
            host=payload.get("host"),
            user=payload.get("user"),
            src_ip=payload.get("id.orig_h"),
            dst_ip=answers[0] if answers else payload.get("id.resp_h"),
            domain=payload.get("query"),
            raw=payload,
        )
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.ZEEK,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.ZEEK.value],
        event_type=f"zeek_{log_type}",
        host=payload.get("host"),
        user=payload.get("user"),
        src_ip=payload.get("id.orig_h"),
        dst_ip=payload.get("id.resp_h"),
        src_port=payload.get("id.orig_p"),
        dst_port=payload.get("id.resp_p"),
        raw=payload,
    )


def parse_suricata(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    alert = payload.get("alert", {}) or {}
    sig_severity = alert.get("severity", 3)
    severity = Severity.HIGH if sig_severity == 1 else Severity.MEDIUM if sig_severity == 2 else Severity.LOW
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.SURICATA,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.SURICATA.value],
        event_type="network_alert",
        severity=severity,
        host=payload.get("host"),
        src_ip=payload.get("src_ip"),
        dst_ip=payload.get("dest_ip"),
        dst_port=payload.get("dest_port"),
        tags=[alert.get("category", "")] if alert.get("category") else [],
        raw=payload,
    )


def parse_active_directory(
    payload: dict[str, Any], timestamp: datetime, tenant_id: str
) -> CanonicalEvent:
    event_id_num = int(payload.get("EventID", 0) or 0)
    event_type = AD_EVENT_TYPES.get(event_id_num, f"ad_event_{event_id_num}")
    severity = Severity.MEDIUM if event_type == "logon_failure" else Severity.INFORMATIONAL
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.ACTIVE_DIRECTORY,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.ACTIVE_DIRECTORY.value],
        event_type=event_type,
        severity=severity,
        host=payload.get("Computer"),
        user=_strip_domain_user(payload.get("TargetUserName") or payload.get("SubjectUserName")),
        src_ip=payload.get("IpAddress"),
        raw=payload,
        tags=[f"logon_type_{payload.get('LogonType')}"] if payload.get("LogonType") else [],
    )


def parse_cloudtrail(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    event_name = payload.get("eventName") or payload.get("event_type", "aws_api_call")
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.CLOUDTRAIL,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.CLOUDTRAIL.value],
        event_type="aws_api_call",
        user=payload.get("user") or (payload.get("userIdentity", {}) or {}).get("userName"),
        src_ip=payload.get("sourceIPAddress") or payload.get("src_ip"),
        cloud_account=payload.get("cloud_account") or payload.get("recipientAccountId"),
        cloud_resource=payload.get("cloud_resource") or payload.get("eventSource"),
        command_line=event_name if not payload.get("command_line") else payload.get("command_line"),
        raw=payload,
    )


def parse_email(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    event_type = payload.get("event_type", "email_received")
    attachments = payload.get("attachments") or []
    urls = payload.get("urls") or []
    first_attachment = attachments[0] if attachments else {}

    verdict = (payload.get("verdict") or "").lower()
    auth_failed = any(payload.get(k) == "fail" for k in ("spf", "dkim", "dmarc"))
    severity = Severity.LOW
    if verdict in {"malicious", "phishing", "spam"} or (auth_failed and verdict != "clean"):
        severity = Severity.MEDIUM

    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.EMAIL,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.EMAIL.value],
        event_type=event_type,
        severity=severity,
        host=payload.get("host"),
        user=payload.get("user") or (payload.get("to", "").split("@")[0] if payload.get("to") else None),
        email_from=payload.get("from"),
        email_to=payload.get("to"),
        email_subject=payload.get("subject"),
        url=payload.get("url") or (urls[0] if urls else None),
        file_hash=payload.get("attachment_hash") or first_attachment.get("sha256"),
        file_path=payload.get("attachment_name") or first_attachment.get("filename"),
        tags=[verdict] if verdict else [],
        raw=payload,
    )


def parse_edr(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    """EDR agents report their own native (snake_case) process-telemetry
    shape rather than Sysmon's PascalCase XML-derived field names, so this is
    a distinct parser from :func:`parse_sysmon` even though both describe
    process-creation-like activity."""

    reputation = (payload.get("reputation") or "").lower()
    severity = Severity.INFORMATIONAL
    if reputation == "malicious":
        severity = Severity.CRITICAL
    elif reputation in {"suspicious", "suspicious_behavior"}:
        severity = Severity.HIGH

    connections = payload.get("network_connections") or []
    first_conn = connections[0] if connections else {}

    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.EDR,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.EDR.value],
        event_type="edr_process_event",
        severity=severity,
        host=payload.get("host"),
        user=_strip_domain_user(payload.get("user")),
        process=payload.get("process_name"),
        process_id=payload.get("pid"),
        parent_process=payload.get("parent_process"),
        parent_process_id=payload.get("ppid"),
        command_line=payload.get("command_line"),
        file_hash=payload.get("sha256"),
        dst_ip=first_conn.get("dst_ip"),
        dst_port=first_conn.get("dst_port"),
        technique_ids=list(payload.get("mitre_techniques") or []),
        tags=[reputation] if reputation else [],
        raw=payload,
    )


def parse_kubernetes(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    event_type = payload.get("event_type", "k8s_audit")
    verb = payload.get("verb", "")
    resource = payload.get("resource", "")
    command_line = payload.get("command_line") or f"{verb} {resource}".strip()
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.KUBERNETES,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.KUBERNETES.value],
        event_type=event_type,
        user=payload.get("user"),
        k8s_namespace=payload.get("k8s_namespace") or payload.get("namespace"),
        k8s_pod=payload.get("k8s_pod") or payload.get("pod"),
        command_line=command_line,
        raw=payload,
    )


def parse_dns(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.DNS,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.DNS.value],
        event_type="dns_query",
        host=payload.get("host"),
        src_ip=payload.get("src_ip") or payload.get("client_ip"),
        domain=payload.get("query"),
        dst_ip=payload.get("answer") or payload.get("resolved_ip"),
        tags=[payload.get("response_code")] if payload.get("response_code") else [],
        raw=payload,
    )


def parse_firewall(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
    action = payload.get("action", "allow")
    severity = Severity.LOW if action == "deny" else Severity.INFORMATIONAL
    return CanonicalEvent(
        tenant_id=tenant_id,
        timestamp=timestamp,
        source=TelemetrySource.FIREWALL,
        source_confidence=SOURCE_CONFIDENCE[TelemetrySource.FIREWALL.value],
        event_type="firewall_connection",
        severity=severity,
        host=payload.get("host"),
        src_ip=payload.get("src_ip"),
        dst_ip=payload.get("dst_ip"),
        dst_port=payload.get("dst_port"),
        tags=[action],
        raw=payload,
    )


def parse_generic(
    source: TelemetrySource,
) -> Callable[[dict[str, Any], datetime, str], CanonicalEvent]:
    def _parser(payload: dict[str, Any], timestamp: datetime, tenant_id: str) -> CanonicalEvent:
        return CanonicalEvent(
            tenant_id=tenant_id,
            timestamp=timestamp,
            source=source,
            source_confidence=SOURCE_CONFIDENCE.get(source.value, 0.5),
            event_type=payload.get("event_type", f"{source.value}_event"),
            host=payload.get("host"),
            user=payload.get("user"),
            src_ip=payload.get("src_ip"),
            dst_ip=payload.get("dst_ip"),
            raw=payload,
        )

    return _parser


PARSERS: dict[str, Callable[[dict[str, Any], datetime, str], CanonicalEvent]] = {
    TelemetrySource.SYSMON.value: parse_sysmon,
    TelemetrySource.EDR.value: parse_edr,
    TelemetrySource.ZEEK.value: parse_zeek,
    TelemetrySource.SURICATA.value: parse_suricata,
    TelemetrySource.ACTIVE_DIRECTORY.value: parse_active_directory,
    TelemetrySource.CLOUDTRAIL.value: parse_cloudtrail,
    TelemetrySource.EMAIL.value: parse_email,
    TelemetrySource.KUBERNETES.value: parse_kubernetes,
    TelemetrySource.DNS.value: parse_dns,
    TelemetrySource.FIREWALL.value: parse_firewall,
}


def get_parser(source: str) -> Callable[[dict[str, Any], datetime, str], CanonicalEvent]:
    if source in PARSERS:
        return PARSERS[source]
    try:
        source_enum = TelemetrySource(source)
    except ValueError:
        source_enum = TelemetrySource.SYNTHETIC
    return parse_generic(source_enum)
