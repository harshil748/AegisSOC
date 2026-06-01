"""Safe action-class taxonomy and playbook catalog (from aegis_common.schema.events.ActionClass)."""

from __future__ import annotations

from aegis_common.schema.events import ActionClass, Severity

DISRUPTIVE_CLASSES = {
    ActionClass.QUARANTINE_RECOMMEND,
    ActionClass.DISABLE_ACCOUNT_RECOMMEND,
    ActionClass.ISOLATE_HOST_RECOMMEND,
    ActionClass.BLOCK_IOC_RECOMMEND,
}

OBJECTIVES = [
    "ransomware",
    "credential_access",
    "lateral_movement",
    "phishing",
    "c2_beacon",
    "recon",
    "benign",
]

PLAYBOOKS: dict[str, dict] = {
    "ransomware": {
        "playbook_id": "PB-CONTAIN-RANSOMWARE",
        "action_class": ActionClass.ISOLATE_HOST_RECOMMEND,
        "title": "Contain suspected ransomware host",
        "risk_if_executed": Severity.HIGH,
    },
    "credential_access": {
        "playbook_id": "PB-CRED-ACCESS-RESPONSE",
        "action_class": ActionClass.ISOLATE_HOST_RECOMMEND,
        "title": "Contain credential-dumping host and reset affected credentials",
        "risk_if_executed": Severity.HIGH,
    },
    "lateral_movement": {
        "playbook_id": "PB-LATERAL-MOVEMENT",
        "action_class": ActionClass.ISOLATE_HOST_RECOMMEND,
        "title": "Isolate hosts participating in lateral movement",
        "risk_if_executed": Severity.MEDIUM,
    },
    "phishing": {
        "playbook_id": "PB-PHISHING-RESPONSE",
        "action_class": ActionClass.DISABLE_ACCOUNT_RECOMMEND,
        "title": "Disable compromised account and quarantine phishing artifact",
        "risk_if_executed": Severity.MEDIUM,
    },
    "c2_beacon": {
        "playbook_id": "PB-BLOCK-C2",
        "action_class": ActionClass.BLOCK_IOC_RECOMMEND,
        "title": "Block command-and-control indicators at the perimeter",
        "risk_if_executed": Severity.MEDIUM,
    },
    "recon": {
        "playbook_id": "PB-COLLECT-EVIDENCE",
        "action_class": ActionClass.COLLECT_DATA,
        "title": "Collect additional evidence for reconnaissance activity",
        "risk_if_executed": Severity.LOW,
    },
    "benign": {
        "playbook_id": None,
        "action_class": ActionClass.IGNORE,
        "title": "No action -- likely benign",
        "risk_if_executed": Severity.INFORMATIONAL,
    },
}

ALLOWED_ACTIONS_BY_OBJECTIVE: dict[str, list[ActionClass]] = {
    "ransomware": [ActionClass.ISOLATE_HOST_RECOMMEND, ActionClass.QUARANTINE_RECOMMEND, ActionClass.ESCALATE],
    "credential_access": [ActionClass.ISOLATE_HOST_RECOMMEND, ActionClass.DISABLE_ACCOUNT_RECOMMEND, ActionClass.ESCALATE],
    "lateral_movement": [ActionClass.ISOLATE_HOST_RECOMMEND, ActionClass.COLLECT_DATA],
    "phishing": [ActionClass.DISABLE_ACCOUNT_RECOMMEND, ActionClass.CREATE_TICKET, ActionClass.NOTIFY],
    "c2_beacon": [ActionClass.BLOCK_IOC_RECOMMEND, ActionClass.COLLECT_DATA],
    "recon": [ActionClass.COLLECT_DATA, ActionClass.ENRICH, ActionClass.NOTIFY],
    "benign": [ActionClass.IGNORE, ActionClass.NOTIFY],
}


def is_disruptive(action_class: ActionClass) -> bool:
    return action_class in DISRUPTIVE_CLASSES
