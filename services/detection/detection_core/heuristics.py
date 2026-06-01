"""Deterministic heuristic scoring layer (stage-2, pre-graph/ML)."""

from __future__ import annotations

from aegis_common.schema.events import CanonicalEvent, Severity

OFF_HOURS = set(range(0, 6)) | {22, 23}

SUSPICIOUS_PROCESS_HINTS = [
    "mimikatz", "procdump", "psexec", "wmic /node", "certutil -urlcache",
    "-enc ", "-encodedcommand", "frombase64string", "sekurlsa",
]

# Context that commonly explains "suspicious" PowerShell as change-managed admin work.
BENIGN_ADMIN_HINTS = [
    "svc-sccm",
    "taskeng.exe",
    "sccm",
    "patch-compliance",
    "patch_compliance",
    "invoke-sccmpatch",
    "monthly-patch",
    "change-managed",
    "softwarecenter",
]


def heuristic_score(event: CanonicalEvent) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    if event.timestamp.hour in OFF_HOURS:
        score += 0.15
        reasons.append("off_hours_activity")

    haystack = " ".join(
        str(v).lower()
        for v in [
            event.command_line,
            event.file_path,
            event.url,
            event.user,
            event.parent_process,
            event.process,
            " ".join(event.tags or []),
            str((event.raw or {}).get("note", "")),
            str((event.raw or {}).get("ParentImage", "")),
        ]
        if v
    )
    if any(h in haystack for h in SUSPICIOUS_PROCESS_HINTS):
        score += 0.35
        reasons.append("suspicious_command_pattern")

    if event.asset_criticality >= 0.8:
        score += 0.2
        reasons.append("high_criticality_asset")

    if event.severity in (Severity.HIGH, Severity.CRITICAL):
        score += 0.25
        reasons.append(f"native_severity_{event.severity.value}")

    if event.intel_matches:
        score += 0.05 * len(event.intel_matches)
        reasons.append("threat_intel_corroboration")

    # Down-weight explainable admin / SCCM-style activity so rule hits alone
    # do not push false positives into the same band as multi-stage attacks.
    benign_hits = [h for h in BENIGN_ADMIN_HINTS if h in haystack]
    if benign_hits and not event.intel_matches:
        score = max(0.0, score - 0.45)
        reasons.append(f"benign_admin_context:{','.join(benign_hits[:3])}")

    return round(min(score, 1.0), 3), reasons
