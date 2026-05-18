#!/usr/bin/env python3
"""Regenerate synthetic multi-source telemetry samples for AegisSOC.

Produces realistic, cross-linked (same hosts/users/IPs recur across sources)
background telemetry as JSONL files under data/samples/. This is "normal SOC
noise" -- the deliberate attack narratives live in data/scenarios/ and are
authored separately so ground truth stays exact.

Usage:
    python scripts/generate_samples.py [--out-dir data/samples] [--seed 1337]

Deterministic given the same --seed, so the corpus is reproducible.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

TENANT_ID = "default"
DOMAIN_FQDN = "aegiscorp.local"
NETBIOS = "AEGISCORP"
EMAIL_DOMAIN = "aegiscorp.com"

FIRST_NAMES = [
    "Elena", "James", "Raj", "Kevin", "Julia", "Maria", "David", "Sarah",
    "Wei", "Fatima", "Carlos", "Aisha", "Tom", "Priya", "Michael", "Grace",
    "Omar", "Nina", "Lucas", "Hannah", "Ivan", "Sofia", "Ben", "Chloe",
    "Anand", "Yuki", "Noah", "Zara", "Diego", "Emma", "Sam", "Layla",
    "Victor", "Mei", "Jonas", "Amara", "Leo", "Ines", "Ahmed", "Ruth",
]
LAST_NAMES = [
    "Martinez", "Chen", "Patel", "Brooks", "Torres", "Nguyen", "Kim",
    "Johnson", "Zhang", "Khan", "Silva", "Ahmed", "Novak", "Rossi",
    "Dubois", "Schmidt", "Yamamoto", "Costa", "Petrov", "Osei",
    "Fischer", "Larsen", "Moreau", "Haddad", "Suzuki", "Wallace",
    "Reyes", "Okafor", "Lindqvist", "Alvarez", "Ferreira", "Baker",
    "Grant", "Hoffman", "Ibrahim", "Jansen", "Kowalski", "Lund",
    "Mendes", "Nakamura",
]

DEPARTMENTS = {
    "finance": {"host_range": (1100, 1149), "subnet": "10.20.10.0/24"},
    "hr": {"host_range": (1150, 1179), "subnet": "10.20.20.0/24"},
    "it": {"host_range": (1180, 1199), "subnet": "10.20.50.0/24"},
    "engineering": {"host_range": (1200, 1249), "subnet": "10.20.30.0/24"},
    "sales": {"host_range": (1250, 1299), "subnet": "10.20.40.0/24"},
}

SERVERS = [
    {"host": "SRV-DC01", "role": "domain_controller", "ip": "10.20.1.10"},
    {"host": "SRV-DC02", "role": "domain_controller", "ip": "10.20.1.11"},
    {"host": "SRV-FILE01", "role": "file_server", "ip": "10.20.1.20"},
    {"host": "SRV-SQL01", "role": "database", "ip": "10.20.1.21"},
    {"host": "SRV-APP01", "role": "application", "ip": "10.20.1.22"},
    {"host": "SRV-WEB01", "role": "web", "ip": "10.20.5.30"},
    {"host": "SRV-EXCH01", "role": "mail", "ip": "10.20.1.24"},
    {"host": "SRV-JMP01", "role": "jump_box", "ip": "10.20.1.25"},
]

# Named identities that also appear as protagonists in data/scenarios/*.json.
# Keeping them in the background corpus makes the graph continuous across
# "normal history" and "the incident".
SCENARIO_ANCHORS = [
    {"first": "Elena", "last": "Martinez", "sam": "emartinez", "dept": "finance", "host": "WKSTN-1147", "role": "Financial Analyst"},
    {"first": "James", "last": "Chen", "sam": "jchen", "dept": "it", "host": "WKSTN-1188", "role": "IT Systems Administrator"},
    {"first": "Raj", "last": "Patel", "sam": "rpatel", "dept": "engineering", "host": "WKSTN-1223", "role": "Software Engineer"},
    {"first": "Kevin", "last": "Brooks", "sam": "kbrooks", "dept": "sales", "host": "WKSTN-1298", "role": "Account Executive"},
    {"first": "Julia", "last": "Torres", "sam": "jtorres", "dept": "it", "host": "SRV-JMP01", "role": "Domain Administrator"},
]

MALICIOUS_DOMAINS = [
    "secure-office365-update.com",
    "cdn-office-update-cache.net",
    "api.cloudsync-telemetry.com",
]
MALICIOUS_IPS = [
    "185.220.101.47",
    "185.220.101.53",
    "45.137.21.9",
    "45.137.21.14",
]
SCANNER_IPS = ["194.26.29.14", "89.248.165.32", "193.32.162.32"]

BENIGN_EXTERNAL_DOMAINS = [
    "login.microsoftonline.com", "outlook.office365.com", "www.google.com",
    "s3.amazonaws.com", "github.com", "slack.com", "zoom.us",
    "cdn.jsdelivr.net", "update.microsoft.com", "www.salesforce.com",
    "api.stripe.com", "docs.google.com", "teams.microsoft.com",
]
BENIGN_EXTERNAL_IPS = [
    "13.107.42.14", "52.96.10.4", "142.250.72.4", "104.16.85.20",
    "20.190.128.10", "151.101.1.140", "34.194.23.11", "8.8.8.8",
]

PROC_TREE = [
    ("C:\\Windows\\explorer.exe", "explorer.exe"),
    ("C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE", "outlook.exe"),
    ("C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE", "winword.exe"),
    ("C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE", "excel.exe"),
    ("C:\\Windows\\System32\\cmd.exe", "cmd.exe"),
    ("C:\\Windows\\System32\\svchost.exe", "svchost.exe"),
    ("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "chrome.exe"),
    ("C:\\Program Files\\Mozilla Firefox\\firefox.exe", "firefox.exe"),
    ("C:\\Windows\\System32\\taskeng.exe", "taskeng.exe"),
    ("C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "powershell.exe"),
]

BENIGN_CHILD_COMMANDS = [
    "C:\\Windows\\System32\\notepad.exe C:\\Users\\{user}\\Documents\\notes.txt",
    "C:\\Program Files\\Microsoft Office\\root\\Office16\\OUTLOOK.EXE /recycle",
    "C:\\Windows\\System32\\svchost.exe -k netsvcs -p",
    "C:\\Windows\\System32\\conhost.exe 0xffffffff -ForceV1",
    "C:\\Windows\\System32\\dllhost.exe /Processid:{{guid}}",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe --type=renderer",
    "C:\\Windows\\System32\\SearchProtocolHost.exe Global\\UsGthrFltPipeMssGthrPipe1",
]

rng = random.Random()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def random_ts(start: datetime, end: datetime) -> datetime:
    delta = end - start
    seconds = rng.uniform(0, delta.total_seconds())
    return start + timedelta(seconds=seconds)


def sha256_like() -> str:
    return "".join(rng.choice(string.hexdigits.lower()) for _ in range(64))


def md5_like() -> str:
    return "".join(rng.choice(string.hexdigits.lower()) for _ in range(32))


def build_users() -> list[dict]:
    users = []
    used_sams = set()
    for anchor in SCENARIO_ANCHORS:
        users.append({
            "sam": anchor["sam"],
            "first": anchor["first"],
            "last": anchor["last"],
            "dept": anchor["dept"],
            "host": anchor["host"],
            "role": anchor["role"],
            "email": f"{anchor['first'].lower()}.{anchor['last'].lower()}@{EMAIL_DOMAIN}",
        })
        used_sams.add(anchor["sam"])

    dept_names = list(DEPARTMENTS.keys())
    for dept in dept_names:
        lo, hi = DEPARTMENTS[dept]["host_range"]
        n_users = (hi - lo + 1) - sum(1 for a in SCENARIO_ANCHORS if a["dept"] == dept)
        for i in range(max(0, n_users)):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            sam = (first[0] + last).lower()
            suffix = 1
            base_sam = sam
            while sam in used_sams:
                suffix += 1
                sam = f"{base_sam}{suffix}"
            used_sams.add(sam)
            host_num = lo + i + sum(1 for a in SCENARIO_ANCHORS if a["dept"] == dept)
            users.append({
                "sam": sam,
                "first": first,
                "last": last,
                "dept": dept,
                "host": f"WKSTN-{host_num}",
                "role": f"{dept.title()} Staff",
                "email": f"{first.lower()}.{last.lower()}@{EMAIL_DOMAIN}",
            })
    return users


def build_host_ip_map(users: list[dict]) -> dict:
    mapping = {}
    server_hosts = {s["host"]: s["ip"] for s in SERVERS}
    for u in users:
        if u["host"] in server_hosts:
            mapping[u["host"]] = server_hosts[u["host"]]
            continue
        subnet = ipaddress.ip_network(DEPARTMENTS[u["dept"]]["subnet"])
        host_num = int(u["host"].split("-")[1])
        lo, _ = DEPARTMENTS[u["dept"]]["host_range"]
        offset = (host_num - lo) % (subnet.num_addresses - 3) + 10
        ip = str(subnet.network_address + offset)
        mapping[u["host"]] = ip
    for s in SERVERS:
        mapping[s["host"]] = s["ip"]
    return mapping


def jsonl_write(path: Path, records: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
    return len(records)


# --------------------------------------------------------------------------
# Source generators
# --------------------------------------------------------------------------

def gen_sysmon(users, host_ip, start, end, n) -> list[dict]:
    out = []
    for _ in range(n):
        u = rng.choice(users)
        host = u["host"]
        ts = random_ts(start, end)
        kind = rng.choices(
            ["process_create", "network_connect", "file_create", "registry_event"],
            weights=[45, 25, 20, 10],
        )[0]
        pid = rng.randint(1000, 65000)
        ppid = rng.randint(500, 999)
        parent_path, parent_name = rng.choice(PROC_TREE)
        rec = {
            "tenant_id": TENANT_ID,
            "source": "sysmon",
            "timestamp": iso(ts),
            "event": {},
        }
        if kind == "process_create":
            child_cmd = rng.choice(BENIGN_CHILD_COMMANDS).format(user=u["sam"], guid=str(uuid.uuid4()))
            rec["event"] = {
                "EventID": 1,
                "Computer": f"{host}.{DOMAIN_FQDN}",
                "User": f"{NETBIOS}\\{u['sam']}",
                "Image": child_cmd.split(" ")[0],
                "CommandLine": child_cmd,
                "ParentImage": parent_path,
                "ParentCommandLine": parent_path,
                "ProcessId": pid,
                "ParentProcessId": ppid,
                "IntegrityLevel": "Medium",
                "Hashes": f"SHA256={sha256_like()}",
                "CurrentDirectory": f"C:\\Users\\{u['sam']}\\",
            }
        elif kind == "network_connect":
            dst_domain = rng.choice(BENIGN_EXTERNAL_DOMAINS)
            dst_ip = rng.choice(BENIGN_EXTERNAL_IPS)
            rec["event"] = {
                "EventID": 3,
                "Computer": f"{host}.{DOMAIN_FQDN}",
                "User": f"{NETBIOS}\\{u['sam']}",
                "Image": rng.choice(["chrome.exe", "firefox.exe", "outlook.exe", "teams.exe"]),
                "ProcessId": pid,
                "SourceIp": host_ip.get(host, "10.20.0.1"),
                "SourcePort": rng.randint(49152, 65535),
                "DestinationIp": dst_ip,
                "DestinationPort": rng.choice([443, 443, 443, 80]),
                "DestinationHostname": dst_domain,
                "Protocol": "tcp",
            }
        elif kind == "file_create":
            fname = rng.choice(["report.xlsx", "notes.docx", "budget.pptx", "backup.zip", "meeting_minutes.pdf"])
            rec["event"] = {
                "EventID": 11,
                "Computer": f"{host}.{DOMAIN_FQDN}",
                "User": f"{NETBIOS}\\{u['sam']}",
                "Image": rng.choice([p for p, _ in PROC_TREE]),
                "ProcessId": pid,
                "TargetFilename": f"C:\\Users\\{u['sam']}\\Documents\\{fname}",
                "CreationUtcTime": iso(ts),
            }
        else:
            rec["event"] = {
                "EventID": 13,
                "Computer": f"{host}.{DOMAIN_FQDN}",
                "User": f"{NETBIOS}\\{u['sam']}",
                "Image": "C:\\Windows\\System32\\svchost.exe",
                "ProcessId": pid,
                "TargetObject": rng.choice([
                    "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\OneDriveSync",
                    "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                    "HKCU\\Software\\Microsoft\\Office\\16.0\\Common\\General",
                ]),
                "EventType": "SetValue",
                "Details": "DWORD (0x00000001)",
            }
        out.append(rec)
    return out


def gen_zeek_conn(users, host_ip, start, end, n) -> list[dict]:
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        src_ip = host_ip.get(u["host"], "10.20.0.1")
        internal = rng.random() < 0.35
        dst_ip = rng.choice(list(host_ip.values())) if internal else rng.choice(BENIGN_EXTERNAL_IPS)
        proto = rng.choices(["tcp", "udp"], weights=[80, 20])[0]
        dst_port = rng.choice([443, 443, 80, 445, 3389, 22, 53, 8080]) if internal else rng.choice([443, 443, 80])
        duration = round(rng.uniform(0.01, 45.0), 3)
        orig_bytes = rng.randint(40, 500000)
        resp_bytes = rng.randint(40, 900000)
        out.append({
            "tenant_id": TENANT_ID,
            "source": "zeek",
            "timestamp": iso(ts),
            "event": {
                "log_type": "conn",
                "ts": ts.timestamp(),
                "uid": f"C{uuid.uuid4().hex[:16]}",
                "id.orig_h": src_ip,
                "id.orig_p": rng.randint(49152, 65535),
                "id.resp_h": dst_ip,
                "id.resp_p": dst_port,
                "proto": proto,
                "service": {443: "ssl", 80: "http", 53: "dns", 22: "ssh", 445: "smb", 3389: "rdp"}.get(dst_port, "-"),
                "duration": duration,
                "orig_bytes": orig_bytes,
                "resp_bytes": resp_bytes,
                "conn_state": rng.choice(["SF", "S0", "REJ", "RSTO"]),
                "orig_pkts": rng.randint(1, 400),
                "resp_pkts": rng.randint(1, 400),
                "history": rng.choice(["ShADadFf", "ShAFf", "S", "ShAdDaFf"]),
            },
        })
    return out


def gen_zeek_dns(users, host_ip, start, end, n) -> list[dict]:
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        query = rng.choice(BENIGN_EXTERNAL_DOMAINS)
        out.append({
            "tenant_id": TENANT_ID,
            "source": "zeek",
            "timestamp": iso(ts),
            "event": {
                "log_type": "dns",
                "ts": ts.timestamp(),
                "uid": f"C{uuid.uuid4().hex[:16]}",
                "id.orig_h": host_ip.get(u["host"], "10.20.0.1"),
                "id.resp_h": "10.20.1.10",
                "query": query,
                "qtype_name": "A",
                "rcode_name": "NOERROR",
                "answers": [rng.choice(BENIGN_EXTERNAL_IPS)],
                "TTLs": [rng.choice([60.0, 300.0, 3600.0])],
            },
        })
    return out


def gen_zeek_http(users, host_ip, start, end, n) -> list[dict]:
    out = []
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    ]
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        host = rng.choice(BENIGN_EXTERNAL_DOMAINS)
        out.append({
            "tenant_id": TENANT_ID,
            "source": "zeek",
            "timestamp": iso(ts),
            "event": {
                "log_type": "http",
                "ts": ts.timestamp(),
                "uid": f"C{uuid.uuid4().hex[:16]}",
                "id.orig_h": host_ip.get(u["host"], "10.20.0.1"),
                "id.resp_h": rng.choice(BENIGN_EXTERNAL_IPS),
                "method": rng.choice(["GET", "GET", "POST"]),
                "host": host,
                "uri": rng.choice(["/", "/api/v1/status", "/login", "/static/app.js", "/docs/", "/search?q=report"]),
                "user_agent": rng.choice(uas),
                "status_code": rng.choice([200, 200, 200, 304, 302, 404]),
                "resp_mime_types": rng.choice(["text/html", "application/json", "application/javascript"]),
            },
        })
    return out


def gen_suricata(users, host_ip, start, end, n) -> list[dict]:
    signatures = [
        ("ET POLICY curl User-Agent Outbound", "Attempted Information Leak", 3),
        ("ET SCAN Suspicious inbound to mySQL port 3306", "Attempted Information Leak", 2),
        ("ET POLICY SSL/TLS Certificate Observed for legit CDN", "Not Suspicious Traffic", 3),
        ("ET INFO TLS Handshake Failure", "Potentially Bad Traffic", 3),
        ("ET SCAN NMAP OS Detection Probe", "Attempted Information Leak", 2),
        ("ET POLICY Outbound DNS query for RFC1918 style domain", "Potential Corporate Policy Violation", 3),
        ("ET WEB_SERVER Possible SQL Injection Attempt", "Web Application Attack", 1),
    ]
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        sig, cat, sev = rng.choice(signatures)
        src_scan = rng.random() < 0.15
        src_ip = rng.choice(SCANNER_IPS) if src_scan else host_ip.get(u["host"], "10.20.0.1")
        dst_ip = host_ip.get(u["host"], "10.20.0.1") if src_scan else rng.choice(BENIGN_EXTERNAL_IPS)
        out.append({
            "tenant_id": TENANT_ID,
            "source": "suricata",
            "timestamp": iso(ts),
            "event": {
                "flow_id": rng.randint(10**14, 10**15),
                "src_ip": src_ip,
                "src_port": rng.randint(1024, 65535),
                "dest_ip": dst_ip,
                "dest_port": rng.choice([80, 443, 22, 3306, 3389]),
                "proto": "TCP",
                "app_proto": rng.choice(["tls", "http", "-"]),
                "alert": {
                    "action": "allowed",
                    "signature": sig,
                    "signature_id": rng.randint(2000000, 2030000),
                    "category": cat,
                    "severity": sev,
                },
            },
        })
    return out


def gen_ad_auth(users, host_ip, start, end, n) -> list[dict]:
    out = []
    dcs = ["SRV-DC01", "SRV-DC02"]
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        dc = rng.choice(dcs)
        event_id = rng.choices([4624, 4625, 4768, 4769, 4672], weights=[45, 8, 20, 20, 7])[0]
        logon_type = rng.choice([2, 3, 3, 10, 11])
        rec = {
            "tenant_id": TENANT_ID,
            "source": "active_directory",
            "timestamp": iso(ts),
            "event": {
                "EventID": event_id,
                "Computer": f"{dc}.{DOMAIN_FQDN}",
                "TargetUserName": u["sam"],
                "TargetDomainName": NETBIOS,
                "WorkstationName": u["host"],
                "IpAddress": host_ip.get(u["host"], "10.20.0.1"),
                "LogonType": logon_type,
            },
        }
        if event_id == 4625:
            rec["event"]["FailureReason"] = rng.choice([
                "%%2313 Unknown user name or bad password.",
                "%%2311 Account currently disabled.",
            ])
            rec["event"]["Status"] = "0xC000006D"
        elif event_id in (4768, 4769):
            rec["event"]["ServiceName"] = "krbtgt" if event_id == 4768 else rng.choice(["SRV-FILE01$", "SRV-SQL01$", "cifs/SRV-FILE01"])
            rec["event"]["TicketEncryptionType"] = "0x12"
        elif event_id == 4672:
            rec["event"]["PrivilegeList"] = "SeDebugPrivilege SeBackupPrivilege SeRestorePrivilege"
        out.append(rec)
    return out


def gen_cloudtrail(users, host_ip, start, end, n) -> list[dict]:
    admin_users = [u for u in users if u["dept"] == "it"] or users
    event_choices = [
        ("ConsoleLogin", "signin.amazonaws.com"),
        ("GetObject", "s3.amazonaws.com"),
        ("PutObject", "s3.amazonaws.com"),
        ("AssumeRole", "sts.amazonaws.com"),
        ("DescribeInstances", "ec2.amazonaws.com"),
        ("ListUsers", "iam.amazonaws.com"),
        ("CreateAccessKey", "iam.amazonaws.com"),
        ("AttachUserPolicy", "iam.amazonaws.com"),
        ("UpdateTrail", "cloudtrail.amazonaws.com"),
    ]
    out = []
    for _ in range(n):
        u = rng.choice(admin_users if rng.random() < 0.4 else users)
        ts = random_ts(start, end)
        event_name, event_source = rng.choice(event_choices)
        region = rng.choice(["us-east-1", "us-west-2", "eu-west-1"])
        mfa = rng.random() < 0.9
        rec = {
            "tenant_id": TENANT_ID,
            "source": "cloudtrail",
            "timestamp": iso(ts),
            "event": {
                "eventVersion": "1.08",
                "eventTime": iso(ts),
                "eventName": event_name,
                "eventSource": event_source,
                "awsRegion": region,
                "sourceIPAddress": host_ip.get(u["host"], "10.20.0.1") if rng.random() < 0.6 else rng.choice(BENIGN_EXTERNAL_IPS),
                "userIdentity": {
                    "type": "IAMUser",
                    "principalId": f"AID{uuid.uuid4().hex[:16].upper()}",
                    "arn": f"arn:aws:iam::123456789012:user/{u['sam']}",
                    "accountId": "123456789012",
                    "userName": u["sam"],
                },
                "additionalEventData": {"MFAUsed": "Yes" if mfa else "No"},
                "responseElements": None,
                "errorCode": None if rng.random() < 0.92 else "AccessDenied",
                "requestID": str(uuid.uuid4()),
                "eventID": str(uuid.uuid4()),
                "readOnly": event_name.startswith(("Get", "List", "Describe")),
                "managementEvent": True,
            },
        }
        out.append(rec)
    return out


def gen_k8s_audit(users, host_ip, start, end, n) -> list[dict]:
    admin_users = [u for u in users if u["dept"] in ("it", "engineering")] or users
    verbs = ["get", "list", "watch", "create", "update", "delete", "patch"]
    resources = ["pods", "services", "deployments", "configmaps", "secrets", "namespaces", "roles"]
    namespaces = ["default", "payments", "monitoring", "kube-system", "ingestion", "detection"]
    out = []
    for _ in range(n):
        u = rng.choice(admin_users)
        ts = random_ts(start, end)
        verb = rng.choice(verbs)
        resource = rng.choice(resources)
        ns = rng.choice(namespaces)
        status = 200 if rng.random() < 0.93 else rng.choice([403, 404])
        out.append({
            "tenant_id": TENANT_ID,
            "source": "kubernetes",
            "timestamp": iso(ts),
            "event": {
                "kind": "Event",
                "apiVersion": "audit.k8s.io/v1",
                "level": "RequestResponse" if resource == "secrets" else "Metadata",
                "auditID": str(uuid.uuid4()),
                "stage": "ResponseComplete",
                "requestURI": f"/api/v1/namespaces/{ns}/{resource}",
                "verb": verb,
                "user": {"username": f"{u['sam']}@{EMAIL_DOMAIN}", "groups": ["system:authenticated", "aegis:engineers"]},
                "sourceIPs": [host_ip.get(u["host"], "10.20.0.1")],
                "objectRef": {"resource": resource, "namespace": ns, "name": f"{resource[:-1]}-{rng.randint(1,99)}"},
                "responseStatus": {"code": status},
                "requestReceivedTimestamp": iso(ts),
            },
        })
    return out


def gen_email_phishing(users, host_ip, start, end, n) -> list[dict]:
    subjects = [
        "Your invoice is attached", "Weekly team sync notes", "Action required: password expiry",
        "Q3 budget review", "Meeting reschedule", "Shared document: Q3 roadmap",
        "Payroll adjustment confirmation", "IT maintenance window notice",
    ]
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        internal = rng.random() < 0.7
        sender = rng.choice(users)
        from_addr = sender["email"] if internal else f"notifications@{rng.choice(['docusign.net','zoom.us','slack.com'])}"
        spf = "pass" if internal or rng.random() < 0.85 else "fail"
        out.append({
            "tenant_id": TENANT_ID,
            "source": "email",
            "timestamp": iso(ts),
            "event": {
                "message_id": f"<{uuid.uuid4()}@mail.{EMAIL_DOMAIN}>",
                "from": from_addr,
                "to": u["email"],
                "subject": rng.choice(subjects),
                "attachments": [],
                "urls": [],
                "spf": spf,
                "dkim": "pass" if spf == "pass" else "fail",
                "dmarc": "pass" if spf == "pass" else "fail",
                "spam_score": round(rng.uniform(0.0, 3.0), 2),
                "verdict": "clean",
            },
        })
    return out


def gen_firewall_dns(users, host_ip, start, end, n) -> list[dict]:
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        is_dns = rng.random() < 0.5
        src_ip = host_ip.get(u["host"], "10.20.0.1")
        if is_dns:
            out.append({
                "tenant_id": TENANT_ID,
                "source": "dns",
                "timestamp": iso(ts),
                "event": {
                    "log_type": "dns_query",
                    "client_ip": src_ip,
                    "query": rng.choice(BENIGN_EXTERNAL_DOMAINS),
                    "query_type": "A",
                    "resolved_ip": rng.choice(BENIGN_EXTERNAL_IPS),
                    "response_code": "NOERROR",
                },
            })
        else:
            dst_ip = rng.choice(BENIGN_EXTERNAL_IPS)
            out.append({
                "tenant_id": TENANT_ID,
                "source": "firewall",
                "timestamp": iso(ts),
                "event": {
                    "log_type": "traffic",
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "dst_port": rng.choice([443, 80, 53, 123]),
                    "protocol": rng.choice(["tcp", "udp"]),
                    "action": "allow",
                    "rule_name": rng.choice(["ALLOW_OUTBOUND_WEB", "ALLOW_OUTBOUND_DNS", "ALLOW_NTP"]),
                    "bytes_sent": rng.randint(200, 50000),
                    "bytes_received": rng.randint(200, 200000),
                },
            })
    return out


def gen_edr_processes(users, host_ip, start, end, n) -> list[dict]:
    out = []
    for _ in range(n):
        u = rng.choice(users)
        ts = random_ts(start, end)
        parent_path, parent_name = rng.choice(PROC_TREE)
        child_cmd = rng.choice(BENIGN_CHILD_COMMANDS).format(user=u["sam"], guid=str(uuid.uuid4()))
        out.append({
            "tenant_id": TENANT_ID,
            "source": "edr",
            "timestamp": iso(ts),
            "event": {
                "agent_id": f"edr-{uuid.uuid4().hex[:12]}",
                "host": u["host"],
                "user": f"{NETBIOS}\\{u['sam']}",
                "process_name": child_cmd.split(" ")[0].split("\\")[-1],
                "pid": rng.randint(1000, 65000),
                "ppid": rng.randint(500, 999),
                "command_line": child_cmd,
                "parent_process": parent_name,
                "sha256": sha256_like(),
                "signed": True,
                "signer": rng.choice(["Microsoft Windows", "Microsoft Corporation", "Google LLC", "Mozilla Corporation"]),
                "reputation": "known_good",
                "mitre_techniques": [],
                "network_connections": [],
            },
        })
    return out


SOURCES = {
    "sysmon_events.jsonl": (gen_sysmon, 450),
    "zeek_conn.jsonl": (gen_zeek_conn, 350),
    "zeek_dns.jsonl": (gen_zeek_dns, 280),
    "zeek_http.jsonl": (gen_zeek_http, 220),
    "suricata_alerts.jsonl": (gen_suricata, 160),
    "ad_auth.jsonl": (gen_ad_auth, 320),
    "cloudtrail.jsonl": (gen_cloudtrail, 220),
    "k8s_audit.jsonl": (gen_k8s_audit, 160),
    "email_phishing.jsonl": (gen_email_phishing, 140),
    "firewall_dns.jsonl": (gen_firewall_dns, 320),
    "edr_processes.jsonl": (gen_edr_processes, 260),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="data/samples")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--days", type=int, default=21, help="lookback window for background telemetry")
    args = parser.parse_args()

    rng.seed(args.seed)

    out_dir = Path(args.out_dir)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    users = build_users()
    host_ip = build_host_ip_map(users)

    total = 0
    counts = {}
    for filename, (fn, n) in SOURCES.items():
        records = fn(users, host_ip, start, end, n)
        records.sort(key=lambda r: r["timestamp"])
        written = jsonl_write(out_dir / filename, records)
        counts[filename] = written
        total += written

    print(f"Generated {total} background telemetry events across {len(SOURCES)} sources into {out_dir}/")
    for filename, n in counts.items():
        print(f"  {filename:24s} {n:5d} events")
    print(f"Users: {len(users)}  Hosts: {len(host_ip)}  Window: {start.date()} .. {end.date()}")


if __name__ == "__main__":
    main()
