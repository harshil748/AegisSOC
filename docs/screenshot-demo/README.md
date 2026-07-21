# AegisSOC Screenshot Demo

Standalone **HTML + CSS + JS** replica of the Analyst Console for report screenshots. Works fully offline with mock data — no Docker or backend required.

## Quick start

```bash
cd docs/screenshot-demo
python3 -m http.server 8765
```

Open: **http://localhost:8765/index.html**

Or open `index.html` directly in Chrome/Safari (double-click).

## Login

- Username: `analyst`
- Password: `analyst123`

**Skip login** (jump straight to app):

```
index.html?demo=1#/alerts
```

## Deep links for screenshots

| Page | URL hash |
|------|----------|
| Alert Queue | `#/alerts` |
| Cases | `#/cases` |
| Case detail | `#/case-detail/da2d212d-0ebb-4d2c-a8a8-f3fdd7197895` |
| Investigation (graph + triage) | `#/investigate/da2d212d-0ebb-4d2c-a8a8-f3fdd7197895` |
| Response / Approvals | `#/response` |
| Audit Trail | `#/audit` |
| Replay / Demo | `#/replay` |
| Metrics | `#/metrics` |

Example full URL:

```
http://localhost:8765/index.html?demo=1#/investigate/da2d212d-0ebb-4d2c-a8a8-f3fdd7197895
```

## Working features

- Login / sign out
- Sidebar navigation (all 6 workspace pages)
- Alert Queue — search, severity/status filters, click row → Investigation
- Cases — filter, click row → Case detail
- Case detail — Open Investigation Workspace button
- Investigation Workspace — attack-path graph (click nodes for drawer), Triage / Timeline / Evidence tabs
- Response — approve/reject recommendations, approval modal with dry-run toggle
- Audit — expandable rows
- Replay — Run scenario with completed status animation + toast
- Metrics — operational metric cards
- Gateway online pill, user menu, toasts

## Files

- `index.html` — shell
- `styles.css` — theme matching production React UI
- `app.js` — mock data + routing + interactions
