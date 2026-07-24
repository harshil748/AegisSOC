# AegisSOC Analyst Console (Frontend)

Production-minded analyst dashboard for AegisSOC, the AI-assisted SOC triage
platform. Built with **Vite + React + TypeScript**, **React Router**, and
**Cytoscape.js** for attack-path graph visualization. The UI is wired
end-to-end against the `frontend-gateway` REST contract described below; if
the backend isn't running yet, every page still renders correct loading /
empty / error states against the real fetch calls.

## Stack

- Vite 5 + React 18 + TypeScript (strict mode)
- React Router 6 (client-side routing, protected routes)
- Cytoscape.js + `cytoscape-dagre` (attack-path graph, left-to-right layout)
- Plain CSS with a design-token layer (`src/styles/theme.css`) — no CSS
  framework required
- Fetch API wrapper with JWT auth, typed errors, and abort-safe data hooks

## Getting started

```bash
cd frontend
npm install
cp .env.example .env   # adjust VITE_API_URL if the gateway isn't on :8080
npm run dev
```

The dev server runs at **http://localhost:5173**. Requests to `/api/*` are
also proxied to `VITE_API_URL` (default `http://localhost:8080`) by
`vite.config.ts`, so both direct-URL and same-origin proxy setups work
without code changes.

Sign in with the seeded analyst account:

```
username: analyst
password: analyst123
```

Other scripts:

```bash
npm run build      # tsc -b && vite build -> dist/
npm run preview    # preview the production build locally
npm run typecheck  # tsc -b --noEmit
npm run lint       # eslint
```

## Pages

| Route | Page | Description |
| --- | --- | --- |
| `/login` | Login | JWT login form |
| `/alerts` | Alert Queue | Prioritized table (severity, risk score, title, techniques, status, created), filters, click-to-investigate |
| `/investigate/:caseId` | Investigation Workspace | Cytoscape attack-path graph with legend + entity detail drawer, case timeline, evidence panel with provenance, LLM triage report panel |
| `/cases` | Cases | List with search/status/severity filters |
| `/cases/:caseId` | Case Detail | Case summary, linked alerts, ATT&CK techniques, response recommendations, link into the Investigation Workspace |
| `/response` | Response / Approvals | Recommendation cards + approval modal (impact/risk summary, dry-run toggle, approve/reject) |
| `/audit` | Audit Trail | Searchable, expandable audit event log (actor, action, resource, evidence, prompt hash) |
| `/metrics` | Metrics | Ingestion, detection, case, LLM, and response health cards from `/api/metrics` |
| `/demo` | Demo | Three guided scenarios with full pipeline walkthrough (ingest → approve) |

The app shell (`src/components/layout/AppShell.tsx`) provides the sidebar
nav, a live gateway-reachability pill, the signed-in analyst's role badge,
and a toast layer for action feedback (success/error/warning/info) used
throughout the app.

## API contract

All calls go through `src/api/client.ts`, which injects the `Authorization:
Bearer <token>` header, normalizes errors into `ApiError`, and dispatches a
global "session expired" event on `401` so the auth context can force a
re-login. Endpoint modules live in `src/api/*.ts`:

```
POST /api/auth/login                     { username, password } -> { access_token, user }
GET  /api/alerts                         ?severity=&status=&q=&limit=&offset= -> { items, total }
GET  /api/cases                          ?status=&severity=&q=&limit=&offset= -> { items, total }
GET  /api/cases/:id                      -> Case
GET  /api/cases/:id/graph                -> { nodes, edges }
GET  /api/cases/:id/timeline             -> { items }
GET  /api/cases/:id/triage               -> TriageReport
GET  /api/cases/:id/evidence             -> { items }   (evidence panel provenance)
GET  /api/actions                        ?case_id=&status= -> ActionRecommendation[]
POST /api/approvals                      { action_id, case_id, decision, rationale, dry_run } -> ApprovalDecision
GET  /api/audit                          ?q=&actor=&actor_type=&limit=&offset= -> { items, total }
GET  /api/metrics                        -> MetricsSnapshot
```

TypeScript types for every payload mirror the canonical schema in
`packages/common/aegis_common/schema/events.py` and live in
`src/types/domain.ts`, so the frontend and backend stay in sync as the
schema evolves.

## Project structure

```
src/
  api/            fetch client + one module per resource (alerts, cases, actions, audit, metrics, auth)
  components/
    layout/       AppShell, Sidebar, Topbar, ProtectedRoute
    common/       Badges, ConfidenceMeter, loading/empty/error state blocks
    alerts/       AlertFilters, AlertTable
    investigation/AttackGraph (Cytoscape), GraphLegend, EntityDetailPanel, CaseTimeline, EvidencePanel, TriageReportPanel
    response/     RecommendationCard, ApprovalModal
    metrics/      MetricCard
    icons.tsx     inline SVG icon set (no icon-font dependency)
  context/        AuthContext (JWT session), ToastContext (notifications)
  hooks/          useAsync (abort-safe data fetching), useGatewayStatus
  pages/          one component per route
  styles/         theme.css (design tokens), global.css, components.css, layout.css, login.css, investigation.css
  types/          domain.ts (shared TypeScript contracts)
  utils/          format.ts, severity.ts, graphStyle.ts (node/edge color mapping)
```

## Design system

The theme (`src/styles/theme.css`) is a true-black palette with vivid orange
accents — deliberately avoiding steel-blue / AI-glow marketing looks, since
this is a dense analyst tool meant for long shifts:

- High-contrast data tables with sticky headers, hover/selected row states
- A consistent severity scale (critical / high / medium / low / informational)
  reused across badges, graph nodes, and timeline dots
- Cytoscape node colors are keyed by `NodeType` (User, Host, Process, IP,
  Domain, AttackTechnique, Incident, …) via `src/utils/graphStyle.ts`, with a
  legend rendered above the graph and an entity-detail drawer on node click
- Responsive down to ~1180px (sidebar collapses to icons) for laptop SOC
  analyst screens

## Docker

```bash
docker build -t aegissoc-frontend .
docker run -p 8081:80 -e GATEWAY_UPSTREAM=http://frontend_gateway:8080 aegissoc-frontend
```

The image is a two-stage build: `npm run build` produces static assets, then
they're served by nginx (`nginx.conf`). `GATEWAY_UPSTREAM` is resolved at
container start via nginx's template envsubst, so `/api/*` and `/health` are
reverse-proxied to the gateway service without baking its address into the
JS bundle — override it per environment (docker-compose service name, k8s
service DNS, etc.) without rebuilding the image.

## Notes on backend readiness

This frontend is implemented fully against the contract above. If
`frontend-gateway` (or any upstream service) isn't running, pages show a
network-aware error state with a **Retry** button rather than crashing, and
the sidebar's "Gateway" pill flips to *offline*. Login will simply fail with
a clear message until `/api/auth/login` is served.
