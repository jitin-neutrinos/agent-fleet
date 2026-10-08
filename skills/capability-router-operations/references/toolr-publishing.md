# ToolR publishing & product state

Working tree `~/Work/tool-router`; public as **ToolR** (github.com/jitin-neutrinos/ToolR,
master branch). The skill tree is symlinked (`~/toolr -> ~/Work/tool-router`), so the
installed entrypoint always runs the working code — never re-clone after edits.

## Publishing pipeline

```bash
cd ~/Work/tool-router
git -c user.name=hermes -c user.email=hermes@local commit -m "..." && git push
bash tools/deploy.sh            # tarball + installers + checksums -> ~/Work/toolr-www
```

Served by `toolr-www.service` (user unit, `tools/serve-www.py`, 127.0.0.1:8030) behind
the `jitinnair-personal` cloudflared tunnel; hostname `toolr.jitinnair.com` (CNAME added).
One-liners: `curl -fsSL https://toolr.jitinnair.com/install.sh | bash` (mac/linux) and
`irm https://toolr.jitinnair.com/install.ps1 | iex` (Windows, PS 5.1+ — mirrors the
agent-fleet ps1 pattern: TLS12, no PS7 syntax, BOM-free writes, drives the same Python
TUI installer). Windows also gets `route.cmd`/`index.cmd` launcher twins from
`install_launchers` (sh shims don't exec there) — any new launcher must emit both forms.
Cache policy: hash-named artifacts immutable forever; mutable entrypoints
(install.sh, install.ps1, SHA256SUMS) `no-store`. deploy.sh additionally writes
`checksums-$STAMP.txt` — the versioned name matches the IMMUTABLE regex, so the CDN
caches it forever and it is always correct; verifiers should prefer it.

### CDN staleness rules (learned the hard way)

- **Restart the static server after changing its cache policy** — the running process
  keeps the old headers, and the edge caches under THEM. A no-store policy in the file
  does nothing until the unit restarts.
- **Already-poisoned edge objects outlive the origin fix.** Purging them needs a
  Cloudflare API token (none on this machine); the durable workaround is versioned
  filenames for anything verifiers depend on, never waiting for a mutable URL to expire.
- **Cache-busting query strings do NOT bypass a poisoned entry** — the edge caches the
  response per query-key (`/?v=anything` can serve the same stale/404 object with
  `cf-cache-status: HIT`). Only a changed PATH evicts; link users to a versioned or
  subdirectory path (`/landing/`) when the bare path is stale.
- Verify via the CDN (`curl -s https://toolr.jitinnair.com/<file>`), not origin —
  origin-fresh + edge-stale is exactly the state that bites users.

### Landing page deploys

The landing lives at `landing/index.html` in the repo; serve-www maps `/` to it. Two
deploy rules that bit once each:

- **Archive inclusion is not deployment.** Putting a directory in deploy.sh's PAYLOAD
  only puts it in the tarball; every user-facing path needs an explicit `cp -r` into the
  www dir. The payload check passes while the page 404s. After any deploy, `curl` the
  exact user-facing URL and assert on a content substring, not the status code alone.
- **Vision-QA loop before shipping a page**: headless Playwright (screenshot top +
  mid-scroll, count rendered diagram SVGs, click every copy/tab control) → vision_analyze
  on the screenshots with a defect-hunting question → fix → redeploy → re-screenshot.
  The pass finds real layout defects (stretched pills, misaligned card rows, low-
  contrast controls) that markup review misses; expect one fix round.

### Clean-context installer E2E

`git clone` the PUBLIC repo into a scratch dir (never test from the working tree — it
has files a stranger's clone lacks), point `HOME=` at a scratch home with fake harness
dirs (`mkdir fakehome/.claude`), and run the TUI inside it. **Env-var partial isolation
lies**: overriding the router-home var without `HOME=` still writes harness skill dirs,
rulebook blocks and symlinks into the REAL home. After any installer test run, sweep the
real harness dirs for symlinks resolving into the scratch tree and `ln -sfn` them back —
a disposable clone behind a live skill symlink breaks the harness the moment the scratch
dir is deleted.

## Landing revamps: fail-open reveals and the edge-cache override (2026-10-08)

- **GSAP entrances freeze at opacity:0 in throttled/backgrounded tabs** (probe
  harnesses, mobile browsers with the page backgrounded mid-load): the tween
  clock stalls, the hero strands invisible, zero console errors. Gate
  hide-for-animation behind a rAF-alive check — only add the `html.anim` class
  (which carries `.anim .rv{opacity:0}`) after a probe rAF actually fires;
  otherwise the page ships fully visible and static. CSS fallbacks in media
  queries must target `.anim .rv`, not bare `.rv`, or they lose the specificity
  fight when JS half-runs. Verified fail-open: a tab whose rAF never fired
  rendered 0/43 elements hidden.
- **A Cloudflare zone cache rule can override origin `no-store` for HTML**
  (edge answered `cf-cache-status: HIT, age: 24h+`, `max-age=31536000` despite
  origin `Cache-Control: no-store`): bare-URL deploys look live from origin
  while every real visitor gets the pinned old page. Verify with a
  query-busted fetch (`?v=$RANDOM`) compared byte-for-byte against the origin
  file — the mutable-URL twins (`checksums-<stamp>`) dodge this for artifacts,
  but `index.html` itself stays mutable. Purge needs a zone API token; none
  exists on the host, so HTML deploys stay pinned until Jitin supplies one or
  deletes the zone rule.

## Delivery wiring (verified live)

- **Claude Code**: UserPromptSubmit hook (`settings.json`) → `route.py --hook`.
  Enforcement (deny-once PreToolUse `gate.py --check` + PostToolUse `gate.py --loaded`)
  wired and backed up (`settings.json.bak-toolr-enforce`).
- **Hermes gateway (Astra/Android/Telegram/TUI)**: plugin enabled in config.yaml
  `plugins.enabled` — PRESENT-ON-DISK ≠ ENABLED; grep the gateway logs for the card
  marker to prove delivery. `pre_gateway_dispatch` stamps the session model as
  `HERMES_MODEL` for the resolver, and on webui/android surfaces appends an
  astra-canvas block (picks table + decision context) parsed FROM the emitted card —
  display-only, the model still gets the markdown card. Boot activation skips
  gateway-transform hooks: `toolr-rearm.service` (Wants= drop-in on hermes-gateway)
  re-registers the hook ~1 s after every restart; audit trail in `rearm.log`.
- **Authority self-heal**: every route re-verifies the delegation mandate + interception
  shim per detected harness and rewrites undos; repairs land in
  `~/.tool-router/authority-heal.jsonl`. The 75% adoption floor rides in
  `last_route.json` (`adoption.kept/total`) and escalates the deny-once gate below floor.
- **Adoption harvest**: `toolr-adopt.timer` daily 10:45 IST → `scripts/adoptcollect.py`
  → `eval/adoption.jsonl`; layer-3 depth adjustment consumes it once a 24h span exists.
- State dir `~/.tool-router/`: index.json (tokens stripped on save, re-derived on load
  WITH aliases+bodies), `index.dense.npz` (Ollama nomic-embed-text; full rebuild = move
  `.npz` AND `.meta.json` aside), `learned.json` (Skill-load prior, +0.25 clamp 2.0),
  `breaker-*.json` (delete to reset), `last_route.json` (gate's suggestion state),
  `config.json` (`fusion_alpha`, `kind_quota`, `mcp_hints`, `decision`).
