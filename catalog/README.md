# catalog — the store's data layer + web UI

Serves the Agent Fleet Store at https://harness.jitinnair.com/ (via health/status-server.py,
port 8003): a four-page browsable catalog of everything the fleet ships, plus per-item
detail pages with install commands and the official upstream docs.

| Piece | What it does |
|---|---|
| `upstreams.json` | Curated map item → official upstream repo (verified against GitHub). |
| `build-inventory.py` | Scans skills / mcp defs / plugins / harness tools → `inventory.json` (the pages' only data source). Also auto-derives an upstream repo per skill from its own frontmatter (`derive_repo`) — kept only when the fetcher could confirm the repo exists — and emits `derived-repos.json` for the workers. Runs after every sync + daily (agent-fleet-catalog.timer). |
| `upstream-worker.py` | Daily: refreshes stars / last push / HEAD sha / latest release tag for every curated **and derived** repo → `upstream.json`. |
| `docs-worker.py` | Daily: fetches each upstream repo's README (via `gh api` — works for private repos too) → `docs/<owner>__<repo>.json`, change-detected by sha. |
| `md.py` | Small dependency-free, escape-first Markdown → HTML renderer used to render those READMEs. |
| `custom/` | Hand-written pages for our own items (neutrinos-designer, neutrinos-mcp, ponytail, caveman, shell-hitl-gate). Frontmatter: `slug / title / kind / summary / repo / site / install / attach` — `attach` links the page onto a catalog item (e.g. the neutrinos MCP entry). |
| `www/` | The store UI: `index.html` + `app.css` + `app.js` (vanilla ES2020, no build step) + self-hosted brand fonts (DM Sans, Playfair Display, JetBrains Mono — the www.jitinnair.com set). |

Design: www.jitinnair.com brand language — dark `#0a0a0f`, blue accent `#22d3ee` primary,
emerald used sparingly, zero gradients; Playfair headings, DM Sans body, JetBrains Mono meta.

Routes (all served by health/status-server.py):
- `/` `#/skills` `#/mcps` `#/plugins` `#/tools` — public store (hash routing, search, filters, pagination)
- `/item/<kind>/<slug>` — public detail page (`kind`: `skills` | `mcps` | `plugins` | `tools` | `custom`):
  description, facts, install/connect command, upstream repo link with live stats, rendered official docs
- `/api/inventory.json`, `/api/item.json?kind=…&slug=…` — public data
- `/install.sh` — public installer
- `/status`, `/status.json`, `/logs` — admin (basic auth from `~/.config/agent-fleet/health.env`)

Fully dynamic by design: slugs come from item names, stats and docs refresh daily, nothing is
hand-maintained per item — dropping a skill with a github.com URL in its frontmatter into
`skills/` grows its catalog page automatically.

Manual refresh: `python3 catalog/build-inventory.py` (fast) · `python3 catalog/docs-worker.py` ·
`python3 catalog/upstream-worker.py` (hits GitHub via gh, ~a minute). The daily timer runs all
three in order (build → stats → docs → build).
