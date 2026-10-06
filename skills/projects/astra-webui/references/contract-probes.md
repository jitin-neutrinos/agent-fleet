# Live contract probes (read-only) — Astra pages vs the dashboard API

Depth for review/QA passes: prove a page works against the *live* host contract instead of the docs.
All of it is read-only; nothing here mutates state. Login recipe (password from `~/.hermes/.env`, never echoed): `references/qa-auth.md`.

Run probes as FILES in a scratch dir (e.g. `~/Work/astra/scratch/review/probe.py`) — oversized inline one-liners get hard-blocked by the command parser, and a saved script is re-runnable next pass.

## 1. Does the route exist, and with which verb?
- `GET` on a POST-only route answers the app's custom `404 {"detail":"No such API endpoint: <path>"}` — looks identical to a missing route.
- `OPTIONS <path>` → `405` with an `allow:` header (e.g. `allow=POST`) = the route exists; that header names the verb to use. `404` + the custom detail = genuinely missing.
- Source of truth for the whole surface: `grep -rhoP '@router\.(get|post|put|patch|delete)\(\s*"[^"]*"' hermes_cli/web_routers/*.py | sort -u`
- Working session auth for the probe: in-memory `CookieJar` + `POST /auth/password-login` `{"username","password","provider":"basic"}` (the provider id comes from `GET /api/auth/providers`; a wrong id 404s with `Unknown provider`).

## 2. Shape probe (what the page actually reads)
Pattern: authenticate → GET every endpoint a page declares (coverage.json + the `endpoints` arrays in astra-core.js) → print status, top-level keys, and a 160-char body head. Then diff against the JS reads (`res.X`, `data.X`).
Traps seen in the wild:
- `/api/model/options` → `{providers, model, provider}` (no `options` key).
- `/api/ops/checkpoints` → `{sessions, total_bytes}` (no `items`).
- `/api/cron/jobs` → bare list (not `{jobs:[…]}`).
- `/api/env` → `{VAR: value}` map (no `keys` list) — the page's fallback must handle it.
- `/api/skills/hub/official` → `{skills}`; `/api/skills` → bare list of 496 objects with `enabled/usage/category`.
- `/api/logs` → `{file, lines}` (raw strings that need the level/timestamp parser); `/api/files?path=` → `{path,parent,entries,root,locked_root,can_change_path}`.
- `/api/sessions/stats` → `{total, active_store, archived, messages, by_source}`; `/api/analytics/usage?days=7` → `{daily, by_model, by_task, totals, …}`.
A 200 status says nothing about the shape — status probes must be paired with these key checks.

## 3. Method audit of the astra call sites
`grep -n "method:" ~/.hermes/plugins/astra-brand/dashboard/dist/astra-core.js` and match every URL to the router grep above. Same class of bug as the PUT-vs-POST model switch: the UI fails silently (`.then()` with no `.catch`), so only this cross-check catches it.

## 4. Recorders to install BEFORE clicking anything
`cdp('Page.addScriptToEvaluateOnNewDocument', source=…)` with:
- `window.__astraErrs=[]` + `error` / `unhandledrejection` listeners (catches e.g. `rejection: 404 {"detail":"Session not found"}` on a stale chat resume).
- wrapped `console.error` / `console.warn` pushing into the same array.
- `window.alert/confirm/prompt` replaced with loggers that return `false` / `null` so a click can never mutate state.
Then: sweep routes (reset the array per route and read it), or force an error path with `cdp('Network.setBlockedURLs', urls=["*/api/<x>*"])`, reload, read `window.__astraAlerts`.

## 5. Scope + motion probes
- `document.getElementById('astra-root')` — absent in the live DOM, so every rule astra.css scopes to it is dead; walk up from `.astra-rail` to see the real wrapper chain.
- `cdp('Emulation.setEmulatedMedia', features=[{"name":"prefers-reduced-motion","value":"reduce"}])`, then count elements whose computed `transform !== 'none'` before/after. Dropping to 0 = a blanket `transform: none !important` is live and layout transforms are being deleted. Revert with `features=[]`.
- Live-injected theme CSS is readable rule-by-rule: iterate `document.styleSheets` → `cssRules` → look for `ownerNode.id === 'hermes-theme-custom-css'` (the theme YAML block) and grep its text for `gradient(` and `transform: none`.

## 6. What the harness cannot see (say this out loud in any report)
- Row 20 probes GETs on an allow-list only — no mutation verbs, no shapes.
- Row 23 globs only `~/.hermes/plugins/astra-*/dashboard/dist/*.{js,css}` — theme YAML, skin YAML and the login plugin are never scanned (each has carried off-palette hexes/gradients).
- Rows 3/10/13/22 are syntax/shape checks; the rollback drill is never executed, so a broken auth leg (`provider: "basic_auth"`) passes `bash -n`.

## 7. Tool notes that cost time
- Inside `browser_exec`, the workspace path is not a bound variable in `code` — read `os.environ["BH_AGENT_WORKSPACE"]` (or the `workspace` field of the result).
- `page_info()` returns a dict — `json.dumps(...)` it, never slice it as a string.
- `os._exit(0)` at the end of a probe script truncates buffered stdout; `sys.stdout.flush()` instead.
- Put long JS in `js("""(() => {...})()""")` wrapped-IIFE form; a bare arrow function returns the function itself, uncalled.
