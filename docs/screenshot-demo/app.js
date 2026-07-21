/**
 * AegisSOC Screenshot Demo — standalone HTML/CSS/JS mirror of the analyst console.
 * Open index.html in a browser (or: python -m http.server 8765 from this folder).
 */
(() => {
  "use strict";

  const ICONS = {
    shield: `<svg class="brand-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l8 3v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-3z"/></svg>`,
    alert: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 8A6 6 0 106 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>`,
    case: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16v12H4z"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>`,
    response: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    audit: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>`,
    replay: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
    metrics: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3v18h18"/><path d="M7 16l4-6 4 3 5-8"/></svg>`,
    refresh: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>`,
    graph: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><path d="M8.5 16.5L15.5 8.5"/></svg>`,
  };

  const NODE_COLORS = {
    User: "#4f8fd1", Host: "#3fb97f", Process: "#e8c34a", File: "#a78bfa",
    IP: "#f0883e", Domain: "#f87171", Email: "#38bdf8", Alert: "#e5484d",
    AttackTechnique: "#fb7185",
  };

  const CASE_ID_MAIN = "da2d212d-0ebb-4d2c-a8a8-f3fdd7197895";

  const DATA = {
    alerts: [
      {
        alert_id: "ea7d2991-acf5-4a1d-9ea7-4c10c0756a05",
        title: "Mass File Rename/Creation with Ransomware-style Extension",
        description: "Bulk encryption activity detected on file share SRV-FILE01",
        severity: "high",
        status: "open",
        risk: { ensemble_score: 0.66, calibrated_score: 0.66 },
        technique_ids: ["T1486", "T1491.001"],
        case_id: CASE_ID_MAIN,
        created_at: "2026-07-18T14:28:05Z",
        tags: ["ransomware", "impact"],
      },
      {
        alert_id: "a1b2c3d4-1111-2222-3333-444455556666",
        title: "Suspicious PowerShell Encoded Command",
        description: "Encoded PowerShell from scheduled task context",
        severity: "low",
        status: "closed",
        risk: { ensemble_score: 0.22, calibrated_score: 0.22 },
        technique_ids: ["T1059.001"],
        case_id: "case-benign-001",
        created_at: "2026-07-17T09:15:00Z",
        tags: ["false-positive"],
      },
      {
        alert_id: "b2c3d4e5-2222-3333-4444-555566667777",
        title: "Known C2 Domain Contact (Repeat Infrastructure)",
        description: "Outbound connection to domain seen in prior incident INC-2026-0412",
        severity: "high",
        status: "investigating",
        risk: { ensemble_score: 0.78, calibrated_score: 0.78 },
        technique_ids: ["T1071.001", "T1568"],
        case_id: "case-repeat-001",
        created_at: "2026-07-19T11:42:00Z",
        tags: ["c2", "graph-memory"],
      },
      {
        alert_id: "c3d4e5f6-3333-4444-5555-666677778888",
        title: "Phishing Email with Macro-Enabled Attachment",
        description: "User opened invoice.docm from external sender",
        severity: "critical",
        status: "escalated",
        risk: { ensemble_score: 0.91, calibrated_score: 0.91 },
        technique_ids: ["T1566.001", "T1204.002"],
        case_id: "case-phish-001",
        created_at: "2026-07-18T14:20:00Z",
        tags: ["phishing", "initial-access"],
      },
    ],
    cases: [
      {
        case_id: CASE_ID_MAIN,
        title: "Auto-case: Mass File Rename/Creation with Ransomware-style Extension",
        status: "new",
        severity: "high",
        risk_score: 0.66,
        alert_ids: ["ea7d2991-acf5-4a1d-9ea7-4c10c0756a05"],
        entity_ids: 8,
        technique_ids: ["T1486", "T1491.001"],
        assignee: "Alex Analyst",
        updated_at: "2026-07-18T14:28:05Z",
        attack_story: "Process svchost32.exe on SRV-FILE01 created ransom-note files and renamed documents with .locked extension across Finance share.",
      },
      {
        case_id: "case-benign-001",
        title: "Benign: SCCM Patch Compliance Script",
        status: "false_positive",
        severity: "low",
        risk_score: 0.18,
        alert_ids: ["a1b2c3d4-1111-2222-3333-444455556666"],
        entity_ids: 3,
        technique_ids: ["T1059.001"],
        assignee: "Alex Analyst",
        updated_at: "2026-07-17T10:00:00Z",
        attack_story: "Scheduled maintenance PowerShell from signed Microsoft binary; change ticket CHG-8842.",
      },
      {
        case_id: "case-repeat-001",
        title: "Repeat C2 Infrastructure — evil-update.biz",
        status: "investigating",
        severity: "high",
        risk_score: 0.78,
        alert_ids: ["b2c3d4e5-2222-3333-4444-555566667777"],
        entity_ids: 5,
        technique_ids: ["T1071.001"],
        assignee: "Senior Analyst",
        updated_at: "2026-07-19T12:00:00Z",
        attack_story: "Same domain observed in incident INC-2026-0412; graph links prior containment event.",
      },
    ],
    graph: {
      nodes: [
        { node_id: "email-1", node_type: "Email", display_name: "invoice.docm (phishing)", confidence: 0.92 },
        { node_id: "proc-1", node_type: "Process", display_name: "C:\\Windows\\Temp\\svchost32.exe", confidence: 0.9 },
        { node_id: "host-1", node_type: "Host", display_name: "SRV-FILE01.AEGISCORP.LOCAL", confidence: 0.95 },
        { node_id: "file-1", node_type: "File", display_name: "README_RECOVER_FILES.txt", confidence: 0.9 },
        { node_id: "file-2", node_type: "File", display_name: "Finance\\report.xlsx.locked", confidence: 0.88 },
        { node_id: "ip-1", node_type: "IP", display_name: "185.220.101.42", confidence: 0.85 },
        { node_id: "dom-1", node_type: "Domain", display_name: "evil-update.biz", confidence: 0.87 },
        { node_id: "tech-1", node_type: "AttackTechnique", display_name: "T1486 Data Encrypted for Impact", confidence: 0.8 },
      ],
      edges: [
        { edge_id: "e1", edge_type: "emailed", src_id: "email-1", dst_id: "proc-1" },
        { edge_id: "e2", edge_type: "executed", src_id: "host-1", dst_id: "proc-1" },
        { edge_id: "e3", edge_type: "created", src_id: "proc-1", dst_id: "file-1" },
        { edge_id: "e4", edge_type: "modified", src_id: "proc-1", dst_id: "file-2" },
        { edge_id: "e5", edge_type: "connected_to", src_id: "proc-1", dst_id: "ip-1" },
        { edge_id: "e6", edge_type: "resolved_to", src_id: "ip-1", dst_id: "dom-1" },
        { edge_id: "e7", edge_type: "mapped_to_technique", src_id: "proc-1", dst_id: "tech-1" },
      ],
    },
    triage: {
      report_id: "tr-001",
      model_id: "mock-template-v1",
      created_at: "2026-07-18T14:30:00Z",
      groundedness_score: 0.8,
      summary: "Evidence indicates ransomware-style impact on SRV-FILE01: a suspicious process (svchost32.exe) created recovery-note files and renamed Finance documents with a .locked extension. The activity chain aligns with MITRE T1486 (Data Encrypted for Impact) and T1491.001 (Defacement). Network telemetry shows outbound contact to evil-update.biz, consistent with C2 staging prior to encryption.",
      likely_objective: "Bulk encryption of file share / endpoint impact for ransom",
      attack_mapping: [
        { technique_id: "T1486", technique_name: "Data Encrypted for Impact", tactic: "Impact", rationale: "Mass file rename with .locked extension" },
        { technique_id: "T1491.001", technique_name: "Defacement: Internal Defacement", tactic: "Impact", rationale: "Ransom note README_RECOVER_FILES.txt deployed" },
        { technique_id: "T1071.001", technique_name: "Application Layer Protocol: Web Protocols", tactic: "C2", rationale: "HTTP beacon to evil-update.biz" },
      ],
      investigation_queries: [
        "Expand graph neighborhood of proc-1 to depth 2 for lateral movement",
        "Correlate all .locked files created within 15-minute window on SRV-FILE01",
        "Check authentication logs for privilege escalation preceding encryption",
      ],
      containment_recommendation: "Isolate SRV-FILE01 from network, preserve memory dump of proc-1, block evil-update.biz at perimeter.",
      confidence_explanation: "High confidence based on correlated file events, process lineage, and intel match on C2 domain.",
      evidence_cited: ["sysmon-2278cffb", "graph-edge-e3", "intel-dom-evil-update"],
    },
    timeline: [
      { timestamp: "2026-07-18T14:20:00Z", title: "Phishing email delivered", description: "invoice.docm opened by finance.user", category: "email" },
      { timestamp: "2026-07-18T14:23:10Z", title: "Suspicious process started", description: "svchost32.exe from Temp directory", category: "process" },
      { timestamp: "2026-07-18T14:25:10Z", title: "Outbound C2 connection", description: "HTTPS to evil-update.biz", category: "network" },
      { timestamp: "2026-07-18T14:28:05Z", title: "Ransom note created", description: "README_RECOVER_FILES.txt on Finance share", category: "file" },
      { timestamp: "2026-07-18T14:28:30Z", title: "Detection alert fired", description: "Mass file rename rule T1486", category: "detection" },
    ],
    evidence: [
      { evidence_id: "ev-1", kind: "event", summary: "Sysmon file_create: README_RECOVER_FILES.txt", source: "sysmon" },
      { evidence_id: "ev-2", kind: "node", summary: "Process svchost32.exe (confidence 0.9)", source: "graph" },
      { evidence_id: "ev-3", kind: "edge", summary: "proc-1 --created--> file-1", source: "graph" },
      { evidence_id: "ev-4", kind: "intel", summary: "evil-update.biz flagged in threat feed", source: "intel" },
      { evidence_id: "ev-5", kind: "detection", summary: "Sigma rule: mass_file_rename_ransom_ext", source: "detection" },
    ],
    actions: [
      {
        action_id: "act-001",
        case_id: CASE_ID_MAIN,
        title: "Isolate host SRV-FILE01",
        description: "Network isolation via EDR API (dry-run available)",
        impact_summary: "Finance file share unavailable until restored",
        disruptive: true,
        dry_run_default: true,
        confidence: 0.88,
        status: "pending",
        action_class: "isolate_host",
      },
      {
        action_id: "act-002",
        case_id: CASE_ID_MAIN,
        title: "Block domain evil-update.biz",
        description: "Add IoC block at perimeter firewall",
        impact_summary: "Low — blocks known C2 only",
        disruptive: false,
        confidence: 0.92,
        status: "pending",
        action_class: "block_domain",
      },
    ],
    audit: [
      { audit_id: "aud-1", timestamp: "2026-07-18T14:30:05Z", actor: "llm_triage", actor_type: "system", action: "triage_report_generated", resource_type: "case", resource_id: CASE_ID_MAIN, evidence_refs: 5 },
      { audit_id: "aud-2", timestamp: "2026-07-18T14:28:10Z", actor: "detection", actor_type: "system", action: "alert_created", resource_type: "alert", resource_id: "ea7d2991", evidence_refs: 3 },
      { audit_id: "aud-3", timestamp: "2026-07-18T14:31:00Z", actor: "analyst", actor_type: "user", action: "case_viewed", resource_type: "case", resource_id: CASE_ID_MAIN, evidence_refs: 0 },
      { audit_id: "aud-4", timestamp: "2026-07-17T10:05:00Z", actor: "analyst", actor_type: "user", action: "case_closed_false_positive", resource_type: "case", resource_id: "case-benign-001", evidence_refs: 2 },
    ],
    scenarios: [
      {
        scenario_id: "phishing_ransomware_chain",
        name: "Phishing → Ransomware",
        description: "Phishing email delivers a macro-laced document that spawns PowerShell, harvests credentials, moves laterally, then detonates ransomware on a file server.",
        expected_outcome: "Escalates to a critical case with a full attack-path graph and a quarantine/isolate recommendation queued for approval.",
        tags: ["phishing", "credential-access", "lateral-movement", "ransomware"],
      },
      {
        scenario_id: "benign_admin_false_positive",
        name: "Benign Admin PowerShell",
        description: "A scheduled task runs an administrator PowerShell maintenance script that superficially resembles living-off-the-land attacker behavior.",
        expected_outcome: "Low risk score, triage report explains benign rationale, no disruptive action recommended.",
        tags: ["false-positive", "powershell", "scheduled-task"],
      },
      {
        scenario_id: "repeat_attacker_infra",
        name: "Repeat Attacker Infrastructure",
        description: "New alert touches IP/domain infrastructure previously observed in a prior confirmed incident.",
        expected_outcome: "Case links to historical incident via shared entities, risk score boosted by graph history.",
        tags: ["threat-intel", "graph-memory", "repeat-offender"],
      },
    ],
    metrics: {
      ingestion: { events_per_sec: 1240, lag_ms: 42, dlq_count: 0 },
      detection: { alerts_24h: 847, precision: 0.91, fp_rate: 0.07 },
      cases: { open: 12, avg_triage_mins: 4.2, auto_clustered: 0.78 },
      llm: { reports_24h: 34, avg_groundedness: 0.82, cache_hit: 0.41 },
      response: { pending_approvals: 2, approved_24h: 8, dry_run_default: true },
    },
  };

  const state = {
    route: "login",
    params: {},
    user: null,
    alertFilter: { q: "", severity: "", status: "" },
    caseFilter: { q: "", severity: "", status: "" },
    invTab: "triage",
    selectedNode: null,
    auditExpanded: null,
    scenarioStatus: {},
    modal: null,
    dryRun: true,
    toast: null,
    graphZoom: 1,
  };

  const CRUMBS = {
    alerts: "Alert Queue",
    cases: "Cases",
    "case-detail": "Cases",
    investigate: "Investigation Workspace",
    response: "Response / Approvals",
    audit: "Audit Trail",
    replay: "Replay / Demo",
    metrics: "Metrics",
  };

  function esc(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function badge(sev) {
    const map = { critical: "badge-critical", high: "badge-high", medium: "badge-medium", low: "badge-low", informational: "badge-informational" };
    return `<span class="badge ${map[sev] || "badge-neutral"}">${esc(sev)}</span>`;
  }

  function caseStatusBadge(st) {
    const cls = st === "false_positive" ? "badge-neutral" : st === "resolved" ? "badge-success" : "badge-info";
    return `<span class="badge ${cls}">${esc(st.replace(/_/g, " "))}</span>`;
  }

  function riskPct(score) {
    return `${Math.round((score || 0) * 100)}%`;
  }

  function fmtDate(iso) {
    try {
      return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return iso;
    }
  }

  function navigate(route, params = {}) {
    state.route = route;
    state.params = params;
    if (route === "investigate") {
      state.invTab = "triage";
      state.selectedNode = null;
    }
    render();
    history.replaceState(null, "", `#/${route}${params.id ? "/" + params.id : ""}`);
  }

  function toast(msg, type = "success") {
    const el = document.getElementById("toast-stack");
    el.innerHTML = `<div class="toast ${type === "error" ? "error" : type}"><strong>${esc(msg)}</strong></div>`;
    setTimeout(() => { el.innerHTML = ""; }, 3500);
  }

  function renderLogin() {
    return `
      <div class="login-screen">
        <form class="login-card" id="login-form">
          <div class="login-brand">
            ${ICONS.shield}
            <div>
              <h1>AegisSOC</h1>
              <span>Analyst Console</span>
            </div>
          </div>
          <div class="field">
            <label>Username</label>
            <input class="input" name="username" value="analyst" required />
          </div>
          <div class="field">
            <label>Password</label>
            <input class="input" type="password" name="password" value="analyst123" required />
          </div>
          <div class="login-hint">Demo credentials: <strong>analyst</strong> / <strong>analyst123</strong></div>
          <div id="login-error" class="login-error hidden">Invalid credentials</div>
          <button type="submit" class="btn btn-primary btn-block">Sign in</button>
          <div class="login-footer">Screenshot demo — fully offline mock data</div>
        </form>
      </div>`;
  }

  function shell(content, route) {
    const pending = DATA.actions.filter((a) => a.status === "pending").length;
    const nav = (r, label, icon, badgeNum) => `
      <button class="nav-link ${route === r ? "active" : ""}" data-nav="${r}">
        ${icon}<span>${label}</span>${badgeNum ? `<span class="nav-badge">${badgeNum}</span>` : ""}
      </button>`;
    return `
      <div class="app-shell">
        <aside class="sidebar">
          <div class="brand">${ICONS.shield}<div class="brand-text"><strong>AegisSOC</strong><span>Analyst Console</span></div></div>
          <div class="nav-section-label">Workspace</div>
          ${nav("alerts", "Alert Queue", ICONS.alert)}
          ${nav("cases", "Cases", ICONS.case)}
          ${nav("response", "Response", ICONS.response, pending || "")}
          ${nav("audit", "Audit Trail", ICONS.audit)}
          ${nav("replay", "Replay / Demo", ICONS.replay)}
          ${nav("metrics", "Metrics", ICONS.metrics)}
        </aside>
        <header class="topbar">
          <div class="topbar-title">AegisSOC <span class="crumb-sep">/</span> <span class="crumb-current">${CRUMBS[route] || route}</span></div>
          <div class="topbar-right">
            <div class="env-pill"><span class="dot"></span> Gateway online</div>
            <div class="user-menu" id="sign-out">
              <div class="avatar">AA</div>
              <div class="user-menu-info"><strong>Alex Analyst</strong><span>analyst</span></div>
            </div>
          </div>
        </header>
        <main class="main-content">${content}</main>
      </div>`;
  }

  function renderAlerts() {
    let items = [...DATA.alerts];
    const f = state.alertFilter;
    if (f.q) items = items.filter((a) => (a.title + a.description).toLowerCase().includes(f.q.toLowerCase()));
    if (f.severity) items = items.filter((a) => a.severity === f.severity);
    if (f.status) items = items.filter((a) => a.status === f.status);
    items.sort((a, b) => b.risk.calibrated_score - a.risk.calibrated_score);

    const rows = items.map((a) => `
      <tr class="clickable" data-investigate="${esc(a.case_id || a.alert_id)}">
        <td>${badge(a.severity)}</td>
        <td class="text-mono">${riskPct(a.risk.calibrated_score)}</td>
        <td><div>${esc(a.title)}</div><div class="row-sub">${esc(a.description)}</div></td>
        <td>${a.technique_ids.map((t) => `<span class="tag-chip">${esc(t)}</span>`).join("")}</td>
        <td><span class="badge badge-outline">${esc(a.status)}</span></td>
        <td class="text-tertiary">${fmtDate(a.created_at)}</td>
      </tr>`).join("");

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Alert Queue</h1><p>Prioritized alerts ranked by ensemble risk score. Click a row to open the investigation workspace.</p></div>
          <div class="page-actions"><button class="btn btn-sm" id="refresh-btn">${ICONS.refresh} Refresh</button></div>
        </div>
        <div class="filter-bar">
          <input class="input" placeholder="Search title, technique, entity…" id="alert-q" value="${esc(f.q)}" style="flex:1;min-width:200px" />
          <select class="select" id="alert-sev"><option value="">All severities</option>
            ${["critical","high","medium","low","informational"].map((s) => `<option value="${s}" ${f.severity===s?"selected":""}>${s}</option>`).join("")}
          </select>
          <select class="select" id="alert-st"><option value="">All statuses</option>
            ${["open","investigating","escalated","closed","false_positive"].map((s) => `<option value="${s}" ${f.status===s?"selected":""}>${s}</option>`).join("")}
          </select>
          <span class="text-tertiary" style="font-size:12px">${items.length} alerts</span>
        </div>
        <div class="panel"><div class="data-table-wrap"><table class="data-table">
          <thead><tr><th>Severity</th><th>Risk</th><th>Title</th><th>Techniques</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div></div>
      </div>`, "alerts");
  }

  function renderCases() {
    let items = [...DATA.cases];
    const f = state.caseFilter;
    if (f.q) items = items.filter((c) => c.title.toLowerCase().includes(f.q.toLowerCase()));
    if (f.severity) items = items.filter((c) => c.severity === f.severity);
    if (f.status) items = items.filter((c) => c.status === f.status);

    const rows = items.map((c) => `
      <tr class="clickable" data-case="${esc(c.case_id)}">
        <td>${badge(c.severity)}</td>
        <td class="text-mono">${riskPct(c.risk_score)}</td>
        <td><div>${esc(c.title)}</div></td>
        <td>${caseStatusBadge(c.status)}</td>
        <td>${c.alert_ids.length}</td>
        <td>${esc(c.assignee || "—")}</td>
        <td class="text-tertiary">${fmtDate(c.updated_at)}</td>
      </tr>`).join("");

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Cases</h1><p>Investigation cases clustered from correlated alerts.</p></div>
        </div>
        <div class="filter-bar">
          <input class="input" placeholder="Search cases…" id="case-q" value="${esc(f.q)}" style="flex:1" />
          <select class="select" id="case-sev"><option value="">All severities</option>
            ${["critical","high","medium","low"].map((s) => `<option value="${s}" ${f.severity===s?"selected":""}>${s}</option>`).join("")}
          </select>
        </div>
        <div class="panel"><div class="data-table-wrap"><table class="data-table">
          <thead><tr><th>Severity</th><th>Risk</th><th>Title</th><th>Status</th><th>Alerts</th><th>Assignee</th><th>Updated</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div></div>
      </div>`, "cases");
  }

  function renderCaseDetail() {
    const c = DATA.cases.find((x) => x.case_id === state.params.id) || DATA.cases[0];
    const linked = DATA.alerts.filter((a) => c.alert_ids.includes(a.alert_id));
    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Case Detail</h1><p class="text-mono">${esc(c.case_id)}</p></div>
          <div class="page-actions">
            <button class="btn btn-primary btn-sm" data-investigate="${esc(c.case_id)}">${ICONS.graph} Open Investigation Workspace</button>
          </div>
        </div>
        <div class="panel panel-body">
          <div class="flex gap-3 wrap items-center" style="margin-bottom:16px">
            ${badge(c.severity)} ${caseStatusBadge(c.status)}
            <div class="risk-stat"><span>Risk</span><span>${riskPct(c.risk_score)}</span></div>
            <div class="risk-stat"><span>Assignee</span><span>${esc(c.assignee)}</span></div>
          </div>
          <h2 style="font-size:15px;margin-bottom:8px">${esc(c.title)}</h2>
          <p class="text-secondary" style="margin-bottom:16px">${esc(c.attack_story)}</p>
          <div class="panel-title" style="margin-bottom:8px">Linked Alerts</div>
          ${linked.map((a) => `<span class="tag-chip">${esc(a.alert_id.slice(0,8))}… ${esc(a.title.slice(0,40))}</span>`).join(" ")}
          <div class="panel-title" style="margin:16px 0 8px">MITRE Techniques</div>
          ${c.technique_ids.map((t) => `<span class="tag-chip">${esc(t)}</span>`).join(" ")}
        </div>
      </div>`, "case-detail");
  }

  function layoutGraph() {
    const { nodes, edges } = DATA.graph;
    const positions = {};
    const cols = 4;
    nodes.forEach((n, i) => {
      positions[n.node_id] = { x: 80 + (i % cols) * 170, y: 60 + Math.floor(i / cols) * 120 };
    });
    return { nodes, edges, positions };
  }

  function renderGraphSvg() {
    const { nodes, edges, positions } = layoutGraph();
    const nodeR = 22;
    let svg = `<svg class="graph-svg" viewBox="0 0 720 420" xmlns="http://www.w3.org/2000/svg">`;
    edges.forEach((e) => {
      const s = positions[e.src_id], t = positions[e.dst_id];
      if (!s || !t) return;
      const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
      svg += `<line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="#354561" stroke-width="1.5" marker-end="url(#arrow)"/>`;
      svg += `<text class="graph-edge-label" x="${mx}" y="${my - 4}" text-anchor="middle">${esc(e.edge_type.replace(/_/g," "))}</text>`;
    });
    svg += `<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#354561"/></marker></defs>`;
    nodes.forEach((n) => {
      const p = positions[n.node_id];
      const col = NODE_COLORS[n.node_type] || "#7c8ba1";
      const sel = state.selectedNode === n.node_id ? " selected" : "";
      const label = (n.display_name || n.node_id).slice(0, 18);
      svg += `<g class="graph-node${sel}" data-node="${esc(n.node_id)}" transform="translate(${p.x},${p.y})">`;
      svg += `<circle r="${nodeR}" fill="${col}" fill-opacity="0.25" stroke="${col}" stroke-width="2"/>`;
      svg += `<text text-anchor="middle" y="4" fill="#e7edf6" font-size="9" font-weight="600">${esc(n.node_type)}</text>`;
      svg += `<text text-anchor="middle" y="${nodeR + 14}" fill="#a3b1c6" font-size="8">${esc(label)}</text>`;
      svg += `</g>`;
    });
    svg += `</svg>`;
    return svg;
  }

  function renderInvestigate() {
    const caseId = state.params.id || CASE_ID_MAIN;
    const c = DATA.cases.find((x) => x.case_id === caseId) || DATA.cases[0];
    const t = DATA.triage;
    const node = state.selectedNode ? DATA.graph.nodes.find((n) => n.node_id === state.selectedNode) : null;

    let tabContent = "";
    if (state.invTab === "triage") {
      tabContent = `
        <div class="triage-meta"><span>Model: ${esc(t.model_id)}</span><span>•</span><span>${fmtDate(t.created_at)}</span></div>
        <div class="groundedness"><span style="font-size:11px;color:var(--text-tertiary)">Groundedness</span>
          <div class="progress-track"><div class="progress-fill" style="width:${t.groundedness_score*100}%"></div></div>
          <span class="text-mono">${Math.round(t.groundedness_score*100)}%</span></div>
        <div class="triage-section"><h3>Summary</h3><p>${esc(t.summary)}</p></div>
        <div class="triage-section"><h3>Likely Objective</h3><p>${esc(t.likely_objective)}</p></div>
        <div class="triage-section"><h3>ATT&CK Mapping</h3>
          ${t.attack_mapping.map((m) => `<div class="technique-row"><strong>${esc(m.technique_id)}</strong> ${esc(m.technique_name)} <span class="text-tertiary">(${esc(m.tactic)})</span><br/><span class="text-tertiary">${esc(m.rationale)}</span></div>`).join("")}
        </div>
        <div class="triage-section"><h3>Containment Recommendation</h3><p>${esc(t.containment_recommendation)}</p></div>`;
    } else if (state.invTab === "timeline") {
      tabContent = DATA.timeline.map((ev) => `
        <div class="timeline-item">
          <div class="timeline-time">${fmtDate(ev.timestamp)}</div>
          <div><strong>${esc(ev.title)}</strong><div class="text-tertiary">${esc(ev.description)}</div></div>
        </div>`).join("");
    } else {
      tabContent = DATA.evidence.map((ev) => `
        <div class="evidence-item"><div class="evidence-kind">${esc(ev.kind)}</div>${esc(ev.summary)}<div class="text-tertiary">${esc(ev.source)}</div></div>`).join("");
    }

    const drawer = node ? `
      <div class="entity-drawer">
        <button class="close-btn" id="close-drawer">✕</button>
        <h4>${esc(node.node_type)}</h4>
        <p style="font-size:12px;margin-bottom:8px">${esc(node.display_name)}</p>
        <div class="kv-box"><div class="k">Confidence</div><div class="v">${Math.round(node.confidence*100)}%</div></div>
        <p class="text-tertiary" style="font-size:11px;margin-top:8px">ID: ${esc(node.node_id)}</p>
      </div>` : "";

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Investigation Workspace</h1><p>Case <span class="text-mono">${esc(caseId)}</span></p></div>
          <div class="page-actions"><button class="btn btn-sm" id="refresh-btn">${ICONS.refresh} Refresh</button></div>
        </div>
        <div class="panel panel-body investigation-summary">
          <div style="min-width:200px"><div style="font-weight:700;font-size:15px">${esc(c.title)}</div>
            <div class="text-tertiary" style="font-size:11px">Assignee: ${esc(c.assignee)}</div></div>
          ${badge(c.severity)} ${caseStatusBadge(c.status)}
          <div class="risk-stat"><span>Risk score</span><span>${riskPct(c.risk_score)}</span></div>
          <div class="risk-stat"><span>Alerts</span><span>${c.alert_ids.length}</span></div>
          <div class="risk-stat"><span>Entities</span><span>${c.entity_ids || 8}</span></div>
          ${c.technique_ids.map((tid) => `<span class="tag-chip">${esc(tid)}</span>`).join("")}
        </div>
        <div class="investigation-grid">
          <div class="panel graph-pane">
            <div class="panel-header"><span class="panel-title">Attack-Path Graph</span></div>
            <div class="panel-body">
              <div class="graph-legend">${Object.entries(NODE_COLORS).slice(0,5).map(([k,v]) => `<div class="legend-item"><span class="legend-dot" style="background:${v}"></span>${k}</div>`).join("")}</div>
              ${renderGraphSvg()}
              ${drawer}
            </div>
          </div>
          <div class="panel side-panel">
            <div class="tab-bar">
              <button class="${state.invTab==="triage"?"active":""}" data-tab="triage">Triage Report</button>
              <button class="${state.invTab==="timeline"?"active":""}" data-tab="timeline">Timeline</button>
              <button class="${state.invTab==="evidence"?"active":""}" data-tab="evidence">Evidence</button>
            </div>
            <div class="tab-panel">${tabContent}</div>
          </div>
        </div>
      </div>`, "investigate");
  }

  function renderResponse() {
    const cards = DATA.actions.map((a) => `
      <div class="card recommendation-card">
        <div class="flex justify-between items-center wrap gap-2">
          <strong>${esc(a.title)}</strong>
          ${a.disruptive ? '<span class="disruptive-badge">Disruptive</span>' : ""}
          <span class="badge badge-warning">${esc(a.status)}</span>
        </div>
        <p class="text-secondary">${esc(a.description)}</p>
        <p class="text-tertiary" style="font-size:12px">Impact: ${esc(a.impact_summary)} · Confidence: ${riskPct(a.confidence)}</p>
        ${a.status === "pending" ? `<div class="rec-actions">
          <button class="btn btn-success btn-sm" data-approve="${esc(a.action_id)}">Approve</button>
          <button class="btn btn-danger btn-sm" data-reject="${esc(a.action_id)}">Reject</button>
        </div>` : ""}
      </div>`).join("");

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Response &amp; Approvals</h1><p>Review AI-recommended actions. Disruptive actions require explicit approval.</p></div>
        </div>
        ${cards}
      </div>`, "response");
  }

  function renderAudit() {
    const rows = DATA.audit.map((a) => {
      const exp = state.auditExpanded === a.audit_id;
      return `
        <tr class="audit-row" data-audit="${esc(a.audit_id)}">
          <td class="text-mono" style="font-size:11px">${fmtDate(a.timestamp)}</td>
          <td><span class="badge badge-outline">${esc(a.actor_type)}</span></td>
          <td>${esc(a.actor)}</td>
          <td>${esc(a.action)}</td>
          <td><span class="tag-chip">${esc(a.resource_type)}:${esc(a.resource_id.slice(0,8))}</span></td>
          <td>${a.evidence_refs}</td>
        </tr>
        ${exp ? `<tr><td colspan="6"><div class="audit-detail">${esc(JSON.stringify(a, null, 2))}</div></td></tr>` : ""}`;
    }).join("");

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Audit Trail</h1><p>Append-only log of detections, AI recommendations, and analyst decisions.</p></div>
        </div>
        <div class="filter-bar">
          <input class="input" placeholder="Search audit events…" style="flex:1" />
          <select class="select"><option>All actor types</option><option>user</option><option>system</option></select>
        </div>
        <div class="panel"><div class="data-table-wrap"><table class="data-table">
          <thead><tr><th>Timestamp</th><th>Actor Type</th><th>Actor</th><th>Action</th><th>Resource</th><th>Evidence</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div></div>
      </div>`, "audit");
  }

  function renderReplay() {
    const cards = DATA.scenarios.map((s) => {
      const st = state.scenarioStatus[s.scenario_id] || "idle";
      const msg = st === "completed"
        ? "Scenario replayed into the pipeline; check Alert Queue and Cases."
        : st === "running" ? "Replaying telemetry…" : "";
      return `
        <div class="card scenario-card">
          <div class="flex justify-between items-center">
            <strong>${esc(s.name)}</strong>
            <span class="scenario-status ${st}">${st}</span>
          </div>
          <p class="text-secondary">${esc(s.description)}</p>
          <p class="text-tertiary" style="font-size:12px"><strong>Expected:</strong> ${esc(s.expected_outcome)}</p>
          <div class="tags">${s.tags.map((t) => `<span class="tag-chip">${esc(t)}</span>`).join("")}</div>
          ${msg ? `<div class="scenario-msg ${st === "completed" ? "" : ""}">${esc(msg)}</div>` : ""}
          <button class="btn btn-primary btn-sm" data-scenario="${esc(s.scenario_id)}" ${st==="running"?"disabled":""}>${ICONS.replay} Run scenario</button>
        </div>`;
    }).join("");

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Replay / Demo</h1><p>Replay seeded telemetry for three canonical demo scenarios to validate detection, triage, and response end-to-end.</p></div>
        </div>
        <div class="scenario-grid">${cards}</div>
        <div class="panel panel-body" style="margin-top:8px">
          <div class="panel-title" style="margin-bottom:8px">About Replay Mode</div>
          <p class="text-secondary">Replay injects synthetic Sysmon, email, and network events through the ingestion pipeline. Scenarios are ground-truth labeled for evaluation.</p>
        </div>
      </div>`, "replay");
  }

  function renderMetrics() {
    const m = DATA.metrics;
    const section = (title, items) => `
      <div class="metrics-section"><h2>${title}</h2>
        <div class="metrics-grid">${items.map(([l,v,s]) => `
          <div class="metric-card"><div class="label">${l}</div><div class="value">${v}</div>${s?`<div class="sub">${s}</div>`:""}</div>`).join("")}
        </div></div>`;

    return shell(`
      <div class="page">
        <div class="page-header">
          <div class="page-heading"><h1>Metrics</h1><p>Operational snapshot from Prometheus-style service metrics.</p></div>
          <div class="page-actions"><button class="btn btn-sm" id="refresh-btn">${ICONS.refresh} Refresh</button></div>
        </div>
        ${section("Ingestion", [["Events/sec", m.ingestion.events_per_sec, "p95 lag "+m.ingestion.lag_ms+"ms"], ["DLQ count", m.ingestion.dlq_count, "healthy"]])}
        ${section("Detection & Triage", [["Alerts (24h)", m.detection.alerts_24h, "precision "+m.detection.precision], ["FP rate", (m.detection.fp_rate*100).toFixed(0)+"%", "target <10%"]])}
        ${section("Cases", [["Open cases", m.cases.open, "auto-cluster "+(m.cases.auto_clustered*100)+"%"], ["Avg triage", m.cases.avg_triage_mins+" min", ""]])}
        ${section("LLM Reasoning", [["Reports (24h)", m.llm.reports_24h, "groundedness "+m.llm.avg_groundedness], ["Cache hit", (m.llm.cache_hit*100)+"%", ""]])}
        ${section("Response & Approvals", [["Pending", m.response.pending_approvals, ""], ["Approved (24h)", m.response.approved_24h, "dry-run default"]])}
      </div>`, "metrics");
  }

  function renderModal() {
    if (!state.modal) return "";
    const a = DATA.actions.find((x) => x.action_id === state.modal);
    if (!a) return "";
    return `
      <div class="modal-overlay" id="modal-overlay">
        <div class="modal">
          <div class="modal-header"><strong>Approve Action</strong><button class="btn btn-ghost btn-sm" id="modal-close">✕</button></div>
          <div class="modal-body">
            <p><strong>${esc(a.title)}</strong></p>
            <p class="text-secondary">${esc(a.impact_summary)}</p>
            <div class="flex items-center gap-3">
              <span class="text-secondary">Dry run</span>
              <div class="switch ${state.dryRun ? "on" : ""}" id="dry-run-switch"><span class="switch-knob"></span></div>
            </div>
            <div class="field"><label>Rationale</label><textarea class="textarea" placeholder="Approval rationale for audit trail…">Confirmed ransomware indicators on SRV-FILE01. Isolating host per playbook IR-004.</textarea></div>
          </div>
          <div class="modal-footer">
            <button class="btn" id="modal-cancel">Cancel</button>
            <button class="btn btn-success" id="modal-confirm">Confirm approval</button>
          </div>
        </div>
      </div>`;
  }

  function render() {
    const app = document.getElementById("app");
    if (!state.user) {
      app.innerHTML = renderLogin();
      bindLogin();
      return;
    }
    let html = "";
    switch (state.route) {
      case "alerts": html = renderAlerts(); break;
      case "cases": html = renderCases(); break;
      case "case-detail": html = renderCaseDetail(); break;
      case "investigate": html = renderInvestigate(); break;
      case "response": html = renderResponse(); break;
      case "audit": html = renderAudit(); break;
      case "replay": html = renderReplay(); break;
      case "metrics": html = renderMetrics(); break;
      default: html = renderAlerts(); break;
    }
    app.innerHTML = html;
    document.getElementById("modal-root").innerHTML = renderModal();
    bindShell();
  }

  function bindLogin() {
    document.getElementById("login-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const u = fd.get("username"), p = fd.get("password");
      if (u === "analyst" && p === "analyst123") {
        state.user = { username: "analyst", role: "analyst" };
        navigate("alerts");
        toast("Signed in as analyst");
      } else {
        document.getElementById("login-error")?.classList.remove("hidden");
      }
    });
  }

  function bindShell() {
    document.querySelectorAll("[data-nav]").forEach((el) => {
      el.addEventListener("click", () => navigate(el.dataset.nav));
    });
    document.getElementById("sign-out")?.addEventListener("click", () => {
      state.user = null;
      state.route = "login";
      render();
    });
    document.getElementById("refresh-btn")?.addEventListener("click", () => {
      toast("Data refreshed");
      render();
    });

    document.getElementById("alert-q")?.addEventListener("input", (e) => { state.alertFilter.q = e.target.value; render(); });
    document.getElementById("alert-sev")?.addEventListener("change", (e) => { state.alertFilter.severity = e.target.value; render(); });
    document.getElementById("alert-st")?.addEventListener("change", (e) => { state.alertFilter.status = e.target.value; render(); });
    document.getElementById("case-q")?.addEventListener("input", (e) => { state.caseFilter.q = e.target.value; render(); });
    document.getElementById("case-sev")?.addEventListener("change", (e) => { state.caseFilter.severity = e.target.value; render(); });

    document.querySelectorAll("[data-investigate]").forEach((el) => {
      el.addEventListener("click", () => navigate("investigate", { id: el.dataset.investigate }));
    });
    document.querySelectorAll("[data-case]").forEach((el) => {
      el.addEventListener("click", () => navigate("case-detail", { id: el.dataset.case }));
    });

    document.querySelectorAll("[data-tab]").forEach((el) => {
      el.addEventListener("click", () => { state.invTab = el.dataset.tab; render(); });
    });
    document.querySelectorAll("[data-node]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        state.selectedNode = el.dataset.node;
        render();
      });
    });
    document.getElementById("close-drawer")?.addEventListener("click", () => {
      state.selectedNode = null;
      render();
    });

    document.querySelectorAll("[data-approve]").forEach((el) => {
      el.addEventListener("click", () => { state.modal = el.dataset.approve; state.dryRun = true; render(); });
    });
    document.querySelectorAll("[data-reject]").forEach((el) => {
      el.addEventListener("click", () => {
        const a = DATA.actions.find((x) => x.action_id === el.dataset.reject);
        if (a) { a.status = "rejected"; toast("Action rejected", "warning"); render(); }
      });
    });

    document.getElementById("modal-overlay")?.addEventListener("click", (e) => {
      if (e.target.id === "modal-overlay") { state.modal = null; render(); }
    });
    document.getElementById("modal-close")?.addEventListener("click", () => { state.modal = null; render(); });
    document.getElementById("modal-cancel")?.addEventListener("click", () => { state.modal = null; render(); });
    document.getElementById("dry-run-switch")?.addEventListener("click", () => { state.dryRun = !state.dryRun; render(); });
    document.getElementById("modal-confirm")?.addEventListener("click", () => {
      const a = DATA.actions.find((x) => x.action_id === state.modal);
      if (a) {
        a.status = state.dryRun ? "approved (dry-run)" : "approved";
        state.modal = null;
        toast(state.dryRun ? "Approved (dry-run)" : "Approved and queued for execution");
        render();
      }
    });

    document.querySelectorAll("[data-audit]").forEach((el) => {
      el.addEventListener("click", () => {
        state.auditExpanded = state.auditExpanded === el.dataset.audit ? null : el.dataset.audit;
        render();
      });
    });

    document.querySelectorAll("[data-scenario]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.scenario;
        state.scenarioStatus[id] = "running";
        render();
        setTimeout(() => {
          state.scenarioStatus[id] = "completed";
          toast(`Scenario ${id} replayed`);
          render();
        }, 1500);
      });
    });
  }

  function parseHash() {
    const h = location.hash.replace(/^#\/?/, "") || "login";
    const [route, id] = h.split("/");
    if (route === "login" || !state.user) return;
    state.route = route;
    state.params = id ? { id } : {};
  }

  window.addEventListener("hashchange", () => { parseHash(); render(); });

  // Auto-login for screenshot sessions (?demo=1 skips login)
  if (new URLSearchParams(location.search).get("demo") === "1") {
    state.user = { username: "analyst", role: "analyst" };
    state.route = "alerts";
  }

  parseHash();
  render();
})();
