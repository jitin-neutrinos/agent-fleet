# Fleet topology — kurama-core + office laptop node (verified working)

Two nodes, one shared store. The laptop's Hermes is a full Hermes install (WSL2 Ubuntu with
systemd inside a Windows 11 Entra-managed laptop), pointed at kurama-core's memory server
through a loopback SSH tunnel. Verified end-to-end: tunnel health, MCP tool listing on the
remote node, and the two-way token cross-read.

## Transport

- Direction laptop → kurama-core: systemd unit `agentmemory-tunnel.service` in WSL
  (`/etc/systemd/system/`), `ssh -N -L 3111:127.0.0.1:3111 notjitin@<kurama-core tailnet IP>`
  with the WSL-generated ed25519 key trusted in kurama-core's `authorized_keys`.
  Enabled via `multi-user.target`; boots with WSL systemd.
- Direction kurama-core → laptop: password SSH (`azuread\Name@<tailnet IP>`) into Windows, then
  `wsl.exe -d Ubuntu -u <user> -- bash <script>` for anything inside Linux. publickey is broken
  by the Entra session-reset bug; password works.
- Nothing is exposed on the network: the memory server stays bound to 127.0.0.1 on both ends.

## Laptop node wiring

| Thing | Value |
|---|---|
| Hermes | WSL `~/.hermes/hermes-agent` (v0.21.x), launcher symlinked to `/usr/local/bin/hermes` |
| Model | `model.provider` = desktop's provider, key in WSL `~/.hermes/.env` |
| Memory MCP | stdio: `command: ~/.hermes/node/bin/node`, `args: [~/.hermes/hermes-agent/node_modules/@agentmemory/mcp/bin.mjs]`, `env.AGENTMEMORY_URL=http://127.0.0.1:3111` |
| Node identity | `node.name: office-laptop`, `gateway.enabled: false` (the desktop is the brain) |
| Skills | synced from kurama-core `~/.hermes/skills` (tar over the Windows temp path) |
| Auto-start | Windows scheduled task (ONLOGON) → `wsl.exe -d Ubuntu -- true` → systemd → tunnel |

## Control surface (from kurama-core)

`~/Work/infra/fleet-laptop.sh <cmd>` — needs `LAPTOP_PW` in the environment:

- `health` — tailnet ping, hermes version, tunnel state, memory health through the tunnel.
- `ask "<prompt>"` — ship a prompt file and run a `hermes chat --query-file … --oneshot` on the
  laptop; the ssh session stays open for the duration (WSL kills children of a dropped session).
- `logs` — tail the laptop's last one-shot output (`/tmp/laptop-oneshot.out`, ends `EXIT:<n>`).
- `mem "<text>`" — grep the shared memory from the laptop side through the tunnel.
- `run "<cmd>"` — any bash inside the laptop's WSL.

## Cross-node acceptance (the proof that counts)

1. `health` all green.
2. kurama-core POSTs a random token to `/agentmemory/remember` → 201.
3. `fleet-laptop.sh mem <token>` (or curl the memories list through the tunnel) returns it.
4. Laptop POSTs its own token the same way; kurama-core reads it from `:3111` locally.
5. One `hermes chat --oneshot` on the laptop answers (proves model + config, not just plumbing).

## agent-fleet store auto-update (added 2026-09-14)

- `~/agent-fleet` in WSL = git checkout tracking `origin/main` of private repo `jitin-neutrinos/agent-fleet`,
  over SSH with a **read-only deploy key** (laptop id_ed25519, key id 163245688). No gh/PAT needed.
  git config: `core.sshCommand="ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"`, `pull.ff=only`.
- `update.sh` (in the repo) = pull + mirror skills → `~/.hermes/skills`, `~/.config/opencode/skills`
  (categorised, any-depth readers) and STAGED-FLAT → `~/.claude/skills`, `~/.gemini/config/skills`,
  `~/.gemini/antigravity/global_skills` (depth-1 readers). MCP/plugin changes NOT applied — re-run install.sh.
- System timer `agent-fleet-update.timer` (`/etc/systemd/system`, User=jitinnair,
  `OnCalendar=*-*-* 1,7,13,19:15:00` UTC = :45 IST — 30 min after the desktop sync; Persistent=true).
  Logs: `journalctl -u agent-fleet-update.service`.

## Observability (added 2026-09-14)

- Master: `agent-fleet-health.timer` (hourly) → `health/fleet-health.sh` writes
  `~/agent-fleet-health/{status.json,health.log}` (5-day retention), posts Telegram
  on colour change / store update / daily heartbeat. Also runs at the end of every sync.
- Node: `health/node-report.sh` (end of every update.sh) pushes `node-office-laptop.json`
  to master `~/agent-fleet-health/` over the laptop→master SSH key (no secrets on node).
- Web: `status-server.py` on 127.0.0.1:8003 (harness.jitinnair.com). Agent Fleet Store UI at `/`
  (public; sidebar Skills/MCPs/Plugins/Tools, search/filter/pagination; data = catalog/inventory.json,
  rebuilt by catalog/build-inventory.py on every sync + daily by agent-fleet-catalog.timer together
  with catalog/upstream-worker.py, which tracks each item's official upstream repo). `/status`,
  `/status.json`, `/logs` remain basic-auth. Creds: `~/.config/agent-fleet/health.env`.
- Store detail pages (public): `/item/<kind>/<slug>` (kind: skills|mcps|plugins|tools|custom) —
  install/connect command, upstream link with live stats, official README rendered by `catalog/md.py`
  from `catalog/docs/` (refreshed daily by catalog/docs-worker.py via gh api, private repos included).
  Upstreams are auto-derived per skill from frontmatter (`derive_repo`) and kept only when the fetcher
  can confirm them; hand-written pages for our own items live in `catalog/custom/`. `catalog/README.md`
  is the reference.
- Colours: green = healthy; yellow = late sync / node quiet 8-30h / site one rev behind /
  telegram failing; red = stale sync >14h, repo≠origin, site down, unit down, node silent >30h.
- Telegram bot: @Astral_Hermes_Alerts_bot → chat 8881524728 (wired 2026-09-14). If sends ever
  fail with "chat not found", the owner presses START in the bot once and fleet-health
  auto-discovers the chat from getUpdates; `fleet-health.sh --selftest` verifies delivery.

## Harness skill-discovery contracts (learned 2026-09-14 — install audit)

- Claude Code reads ONLY `~/.claude/skills/<name>/SKILL.md` (depth-1). Nested category folders are
  invisible — an install that rsyncs a categorised tree shows zero skills while every file count passes.
- Antigravity (agy) reads flat `~/.gemini/config/skills/<name>/SKILL.md`; the older
  `~/.gemini/antigravity/global_skills` is NOT read by agy 1.2.2 (kept in sync as a compat copy).
- OpenCode globs recursively (`**/SKILL.md`) — categorised trees are fine; it also reads
  `~/.claude/skills` as a global-compat source. Hermes supports categories natively.
- install.sh + update.sh therefore STAGE A FLAT COPY before installing to claude/agy; duplicate
  basenames keep the first copy and warn (`xlsx`).
- The store repo mirrors `~/.hermes/skills` (sync §1): every skill must be REAL content — cross-tree
  symlinks (e.g. -> `~/.agents/skills/*`) get mirrored as links and break on other machines. Replace
  symlinks with real copies at the source.
- Verify any harness install with the TOOL's own discovery (`claude -p` / `agy -p` probe naming
  skills), never with destination file counts.

## Store health triage — node quiet vs non-conformant

Investigate from the master first; every claim is reproducible from its own artifacts:

1. `~/agent-fleet-health/status.json` — colour, issues list, node summary, store head, sync age.
2. `health.log` tail — when the state changed and what fired.
3. `node-<name>.json` — the node's last self-report; its **mtime is the last contact**. A refreshed
   file (new ts, fresh store_head, `behind_origin:false`) is the proof a returning node caught up.

Rules for reading the flags:

- **"quiet Nh" = no node report arrived in N hours.** Check `tailscale status` ("offline, last
  seen …") before anything else. The update timer lives INSIDE WSL and only fires while the
  distro runs — machine-on ≠ WSL-up, and a sleeping/rebooting laptop misses slots with nothing
  broken. Alert levels: quiet >8h yellow, silent >30h red.
- **Missed runs replay on the next WSL start** (timer Persistent=true). Expect self-heal; confirm
  from the master (fresh node JSON) before scheduling a laptop session or reporting a fault.
- **The master cannot tell "update never ran" from "ran but report push failed"** — mirroring is
  local and the report push is best-effort, so a node can be current while the master shows quiet.
  When reachable, the node's `~/.agent-fleet-health.log` + `journalctl -u agent-fleet-update.service`
  say which happened.
- **"non-conformant / skills differ" was a false positive — FIXED 2026-09-15.** node-report.sh now
  compares the claude count against the store's DISTINCT-basename count (staged-flat mirrors
  collapse duplicate basenames keep-first, e.g. `xlsx`). Verify any flat mirror by name set:
  `bash scripts/flat-mirror-check.sh <store>/skills <flat-dir>`. A non-conformant flag from
  2026-09-15 onward is REAL (a mirror genuinely behind).
- **The desktop's own claude/agy flat mirrors lagged between installs — FIXED 2026-09-15.**
  sync-from-desktop.sh step 6b now runs update.sh against the checkout on every sync, refreshing
  claude/agy (and any other present harness) along with hermes+opencode.
- **node-report only runs on provisioned nodes — FIXED 2026-09-15.** It now requires NODE_NAME in
  `health.env`; the master's env carries only alert credentials, so non-nodes skip cleanly (no
  phantom `node-<master>.json`). Related trap that cost a real revert: **never run update.sh
  standalone on the master while hermes-side skill edits are unsynced** — its repo→hermes mirror
  can revert them; run it via sync (step 6b) instead.

## Caveats

- Both nodes share one provider key → one rolling usage budget; expect 429s under load.
- The laptop node is only alive while the user is logged into Windows (ONLOGON trigger).
- Entra login name is case/exact-form sensitive; try once per session, never loop.
- Laptop password per task: supplied in chat or recovered from the session DB; 0600 copy at kurama-core `~/Work/scratch/laptop-onboard/.af-pw`.
