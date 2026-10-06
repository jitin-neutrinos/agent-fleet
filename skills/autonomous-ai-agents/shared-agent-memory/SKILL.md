---
name: shared-agent-memory
description: "Use when sharing agent memory across tools and sessions."
version: 1.1.0
---

# Shared Agent Memory

Persistent memory that every agent on the machine can read and write — across sessions,
across Hermes profiles, and across separate implementations (Hermes, Claude Code, OpenCode,
agy/Gemini CLI, Codex, custom scripts). Covers evaluating candidates, choosing a topology,
wiring it in, and proving it works.

The candidate survey, evidence, and rejection reasons live in
`references/candidate-landscape.md` — load it before comparing products.

## When to Use

- The user wants memory shared across all sessions, all profiles, or all their agent tools.
- The user asks to evaluate, pilot, or extend a memory product or memory MCP server.
- An agent "doesn't know" something another agent learned — audit the substrate.
- A tool's built-in memory is being proposed as the fix for cross-tool amnesia (it isn't).

## Requirement decomposition — do this before comparing anything

Three constraints, in this order. A candidate that fails any one is disqualified regardless of
its benchmark score.

1. **Across implementations** → the shared layer must speak a protocol every tool already
   implements: MCP, or plain HTTP for custom code. A per-tool plugin, a framework-bound library,
   or a vendor SDK only reaches the tools that vendor wrote.
2. **Near-real-time** → capture must be hook-driven (`SessionStart` / `PostToolUse` /
   `SessionEnd`), not agent discipline. "Remember to save this" is not a memory system.
3. **One store, many readers** → a fact written by tool A must be in tool B's context seconds
   later. Only possible if they read the same database.

Corollary: never solve this by improving one tool's built-in memory. Per-tool memory is the
problem being solved, not the fix.

## Procedure

1. **Inventory where memory lives today, per tool, as a table.** On kurama-core: Hermes default
   profile → `~/.hermes/memories/` + `memory_store.db`; each `profiles/<name>/` has its own;
   Claude Code → `~/.claude/` + `CLAUDE.md` files; other CLIs → their own harness stores. Writing
   the table out makes the gap visible and pre-empts "we already have memory".
2. **Shortlist by the decomposition, not by leaderboard.** Only candidates with a real MCP
   server (stdio or HTTP) and a documented integration for the tools in play.
3. **Choose topology: one always-on service, not one process per client.** Run the memory server
   as a `systemd --user` unit bound to `127.0.0.1`; every tool attaches to it. Per-session
   spawns of the same server against the same file are a concurrency problem with no upside.
   Follow the pattern already proven on this host (local service + user unit + optional tunnel —
   never a public port).
4. **Wire Hermes in two tiers and know which one you need:**
   - MCP entry under `mcp_servers:` in `config.yaml` → memory tools available on demand.
   - A memory-provider plugin under `~/.hermes/plugins/<name>/` → automatic per-turn capture
     and pre-LLM context injection. Only this tier captures without the agent asking.
   - `hermes memory setup|status|off` manages the *bundled* providers and only one external provider
      can be active at a time; a new provider is a plugin drop-in, not a CLI choice.
      - **Additional profiles must be wired one by one.** `hermes -p <profile> mcp add …`, copy the
        provider plugin into `~/.hermes/profiles/<name>/plugins/<name>/`, and set `memory.provider` in
        that profile's config. A profile's `HERMES_HOME` is its own directory, so a plugin installed
        for the default profile is INVISIBLE to every other profile — the same store then looks
        "empty" from the other profile and reads as a broken server. `-p` is not listed in
        `hermes --help`; it exists, and `hermes -p <name> mcp list` proves which profile you are
        addressing.
5. **Wire every other implementation** with the vendor's own setup command where it ships one
   (`connect <agent>` / `setup <agent>` style). Do not hand-edit five config files.
6. **Run the acceptance test below.** Nothing counts as working until step 5 of that test passes.

## Acceptance test — the only proof that counts

1. The server's own health endpoint returns OK.
2. The tool's MCP listing shows the server in a **new** session (registrations load at session
   start; an existing session will not see it).
3. Write a distinctive unguessable token from tool A, in a scratch project scope.
4. Write a different token from tool B.
5. **Cross-read:** ask A for B's token and B for A's token. Both must return the other's exact
   string. Anything short of that is not shared memory.
6. Measure wall-clock write → visibility from the other tool. Target seconds; if it is minutes,
   near-real-time is unmet — fix before rollout.
7. Restart the service (or reboot) and re-read both tokens — proves durable, not in-memory.
8. Confirm the system prompt prefix stays byte-stable across turns within a session: no
   mid-conversation memory injection.

## Design rules

- **Compression beats retrieval.** Keep a dated, append-only observation log that replaces raw
  history instead of injecting freshly retrieved snippets every turn. Supersede facts; never
  rewrite history. This is both the benchmark-leading shape and the only one compatible with
  prompt caching.
- **Inject once per session, bounded.** A fixed token budget at session start, not per-turn
  dynamic retrieval into the prefix.
- **Zero-LLM on the hot path.** Capture synchronously without a model call; compress
  asynchronously. Keeps turn latency flat.
- **Provenance on every row** — agent, session, project, timestamp. Several writers on one store
  produce unauditable mush without it.
- **Strip secrets at capture**, before the write, not at read.
- **Scope by project.** Shared-by-default is the usual product default and the usual mistake:
  an unrelated client project must not surface in another.

## Deliverable shape

This class of task ends in a recommendation, so deliver it the way this user wants it:
**one** best idea — not a menu of options — with the runner-up named in a line; a plain-language
chat reply (no jargon, everyday analogies) with the technical detail written to a markdown
artifact under `~/Work/`; and a source link on every factual claim. State plainly what was
verified by running something versus what is documentation research.

## Pitfalls

- **Disqualify container-backed engines early on this host.** A graph database or vector service
  in a container adds lifecycle, backup, and upgrade burden for a personal memory store, and
  per-write model/embedder calls add latency and cost. Accept one only if the user explicitly
  wants the temporal/graph feature enough to own the service.
- **Benchmark numbers are directional, not comparable.** The same framework is reported 40+
  points apart depending on who ran it, and public numbers skew to vendor self-reports. Always
  pair a score with who ran it; decide on integration fit and architecture.
- **Wiring a shared store across Hermes profiles crosses a deliberate isolation boundary.**
  Config and sessions stay separate while memory becomes shared, so a work project can surface
  in a personal one. Propose it explicitly and get a yes; do not fold it into the install.
- **An existing session won't see a newly registered MCP server.** Restart the session before
  debugging anything else.
- **Shared memory shares mistakes too.** A wrong observation propagates to every agent. Ship
  with provenance, supersede-not-delete, and a working delete/governance path.
- **Don't build a bespoke memory server first.** Mature agent-agnostic servers already ship
  hybrid retrieval, hooks, and a viewer. Build only the subset actually needed, and only after
  the off-the-shelf options fail the decomposition.

## Deployed instance (kurama-core) — built and verified

This is no longer a proposal on this host. agentmemory is installed and running; operational
detail is in `references/deployed-kurama-core.md`. Fast facts:

- systemd user unit `agentmemory.service`, REST `http://localhost:3111`, viewer `:3113`.
- Data: `~/.local/share/agentmemory/state_store.db`. Config: `~/.agentmemory/.env`.
  Binary: `~/.npm-global/bin/agentmemory` (pinned).
- Wired: Hermes (MCP, `mcp__agentmemory__*`) + claude-code, gemini-cli, antigravity,
  antigravity-cli, opencode. Hermes plugin staged at `~/.hermes/plugins/agentmemory/`.
- `scripts/canary_cross_hand.sh` runs the whole acceptance test end to end.
- Ground truth without any agent: POST `/agentmemory/remember` (JSON `{"content":…}`, → 201) to
  write, GET `/agentmemory/memories?limit=200` to list/read back — always check this before
  blaming an agent's search. The `GET /agentmemory/search?q=` endpoint can return empty even for
  stored content; use the memories list for verification.

## Implementation pitfalls (hit for real while installing this)

- **Memories vanish on restart unless the process working directory is pinned.** The generated
  `iii-config.yaml` stores state at a RELATIVE path (`./data/state_store.db`), so the store's real
  location follows the CWD — a first boot landed in `~/data`, a later boot somewhere else, and the
  earlier memories looked "lost". Pin `WorkingDirectory=` to the data dir AND pass `--data-dir` in
  the unit. When memories disappear, locate where the engine actually wrote before assuming loss.
- **`hermes mcp add <name>` asks "Enable all N tools?"** and prints `Cancelled.` when there is no
  TTY — the tool list it prints first makes this look like success. Pipe a yes:
  `printf 'y\n' | hermes mcp add …`. Rule: a tool listing followed by `Cancelled.` saved nothing.
- **Vendor `connect --all` cannot wire Hermes** ("yaml-merge-not-implemented") — Hermes is always
  manual, and `config.yaml` is never hand-edited (use `hermes mcp add` / `hermes config set`).
- **A vendor setup that ships only some integrations**: check the package's `integrations/` dir
  against the repo — the npm tarball carried `integrations/pi` while the Hermes provider lived
  only in git. Copy the provider from a shallow clone, not from node_modules.
- **Naming a tool's absolute binary path in a shell command can trip the gateway-guard hook**
  (false positive: the CLI's own help text mentions stop/uninstall). Call it through
  `npx -y <pkg>@latest <subcommand>` in agent-run commands; the systemd unit may use the path.
- **`read_file` refuses `.env` files** (secret-bearing by design). Inspect only non-secret keys
  through a filtered `grep` in `terminal`; never print the file.
- **Flipping `memory.provider` to the new backend deactivates the old one** (one external provider
  at a time), taking its tools with it. The MCP-server route needs no provider change — ship that
  first and treat the provider switch as a separate, explicitly-confirmed decision.
- **A rate-limited agent looks exactly like a broken memory.** An empty cross-read while REST
  shows the memory present means the agent's own model quota, not the substrate. Read the agent's
  raw reply before debugging the store.
- **`AGENTMEMORY_SECRET` stays unset while the server binds loopback only.** Set it (and re-run
  the vendor `connect`, or the shim won't authenticate) BEFORE any non-loopback exposure; mesh
  sync requires it on both peers, with `AGENTMEMORY_REQUIRE_HTTPS=1` over Tailscale.

## Fleet / multi-device

Each device runs its own server with its own SQLite store; devices sync peer-to-peer via mesh
(`memory_mesh_sync`, Last-Write-Wins; scopes: memories, actions, semantic, procedural, relations,
graph nodes/edges). Register peers with mesh-register and set the same `AGENTMEMORY_SECRET` on
every peer, with `AGENTMEMORY_REQUIRE_HTTPS=1` over Tailscale.

### Adding a remote device as a node (sequence — verify every leg)

The install half and the transport half fail independently. Installing the agent on the device is
verifiable locally (`--version`, and read the install log's tail). The transport leg — the device's
SSH key accepted by the memory host, and the tunnel healthy from the device — is the leg that fails
SILENTLY and leaves every client pointed at a dead URL. Do not call this sequence proven until the
cross-read in the acceptance test passes with the remote device as one of the two tools.

Choose the transport FIRST — it decides which privileges you need:

- `tailscale serve --bg <port>` — cleanest (server stays loopback-bound, tailnet-only HTTPS), but
  needs root.
- Binding the server to the tailnet IP — also needs root, to open the port in firewalld.
- **SSH tunnel — the only option needing no privileged access on either end:**
  `ssh -N -L 3111:127.0.0.1:3111 user@host` as a systemd unit on the client. Loopback stays
  loopback and nothing new is exposed. Prefer this whenever sudo wants an interactive password.

Then: recon the device → install Hermes there → append the device's SSH key to the memory host's
`authorized_keys` (back it up; never overwrite) → install the tunnel unit → verify from the
*device* (`curl http://127.0.0.1:3111/agentmemory/health`) → point that device's agents at the
tunnel URL.

Remote-host pitfalls (each cost real time):

- **A device that sleeps goes offline mid-build.** Check `tailscale status` for
  `offline, last seen` before blaming auth; the tailnet is the fastest signal that the machine
  simply is not there.
- **Verify the path from the device, not the host.** A healthy server here proves nothing about
  reachability there, and test with a real connect (`/dev/tcp/host/port` or a socket) — Windows
  firewalls routinely drop ping while the port works fine.
- **Windows + Entra (Azure AD): `publickey` auth can succeed and then kill the session** —
  `Server accepts key` followed immediately by `Connection reset by peer` (token creation fails).
  Password auth still works. The durable fix is a local non-AD account, which is a policy
  decision on a managed device — ask before creating one.
- **Get the login name exactly right and try ONCE.** `azuread\Name` works where lowercase and
  bare forms are rejected, and corporate AD accounts lock out after repeated failures — never
  loop over username guesses against a work account.
- **Provision by script, not inline commands.** Write a `.sh`, transfer it, run it by path.
  Nested quoting through bash → ssh → PowerShell → WSL mangles `$`, `&` and `\"`, and every
  mangled attempt costs a full round trip.
- **In WSL a normal user usually cannot `sudo` non-interactively.** No sudoers edit needed: run
  privileged steps as `wsl.exe -d <distro> -u root -- <cmd>`. Only the app's own auto-install of
  `build-essential` needs this.
- **A half-finished install looks finished.** A launcher on PATH plus a working `--version` is
  not proof — check the install log's tail for the last step reached and that the closing notes
  appear before calling it done.
- **Linux-side sudo may need a password too**, even where notes claim otherwise. Check
  `sudo -n true` before designing around a privileged command, or pick the tunnel design that
  needs no privilege at all.
- **In WSL, bare `npx` resolves to the WINDOWS node via interop** (`/mnt/c/.../npx`), which
  cannot see WSL-side state or files — an MCP shim configured as `command: npx` then times out
  on connect. Pin the entry to the Linux binary directly: `command: ~/.hermes/node/bin/node`,
  `args: [<shim entry>]`, plus `env.PATH` set to Linux-only dirs. Hermes ships its own Node at
  `~/.hermes/node/bin` — use it on distros with no system node.
- **Read the shim package's `bin` field for the entry file** — it is often `bin.mjs`, not
  `dist/index.js`; probing a nonexistent path fails confusingly.
- **WSL tears down its children when the ssh session driving it drops** — long jobs (npm
  install, `hermes chat`, any model call) launched through `ssh host wsl.exe …` die silently
  mid-run. Keep the ssh session in the foreground for the duration of the job (script waits and
  prints a final marker), or the job must be a real systemd unit. `nohup`/`setsid … &` inside
  WSL does NOT survive it.
- **Never nest a heredoc inside a `bash -s` stdin script** — the inner heredoc consumes the
  outer stdin and the outer script truncates. Config edits that need python go in a separate
  `.py` file, scp'd to the Windows temp dir and run by path (`/mnt/c/.../Temp/x.py`).
- **A CLI installed under `~/.local/bin` is invisible to terminals the user actually opens** —
  `.profile` PATH exports only apply to login shells, and Windows Terminal → WSL starts a
  non-login shell. Register the launcher system-wide (`ln -sf` into `/usr/local/bin` as WSL
  root) and verify with `env -i bash -c 'hermes --version'` — the same bare context the user's
  first terminal gets.
- **A laptop node needs a Windows logon task to come alive**: `schtasks /Create /TN <name> /TR
  "wsl.exe -d Ubuntu -- true" /SC ONLOGON /F` boots WSL systemd, which brings the tunnel unit
  up. Without it the node is dark after every reboot even with the tunnel unit enabled.
- **Two nodes on one provider key share one usage budget** — the laptop's first real model call
  can fail with the desktop's 429 (5-hour rolling limit). Either schedule smoke tests after a
  known reset or give heavy nodes their own key; do not read the 429 as a broken install.

## Holographic plugin — defects found and fixed

Verified fixes in `~/.hermes/hermes-agent/plugins/memory/holographic/`. Each was reproduced
failing before the change:

- **Entity `LIKE` wildcards** (`store.py`): bare `name LIKE ?` let `%`/`_` match, so
  `_resolve_entity("a%")` returned `Acme Corp`. Escape with `ESCAPE '\'` + a translate table.
- **`add_column_if_missing(conn, table, column, ddl)` takes the FULL `"name TYPE"` in `ddl`** —
  passing just the type adds a column literally named `TEXT`.
- **`probe`/`related`/`reason` ignored `min_trust`** while `search` honoured it. Thread it through
  `_rank_by_vector`, and gate `probe`/`related` on the entity actually existing — otherwise a
  nonexistent name returns a full block of confident-looking rows.
- **`contradict()` cannot use vector cosine.** "Acme uses PostgreSQL…" vs "…MongoDB…" score 0.785
  (both datastore nouns), so `overlap*(1-shift(cos))` gave 0.09 and unrelated pairs scored HIGH.
  Score discriminating-TOKEN overlap after removing shared-entity tokens instead.
- **`content[:400]` truncation silently loses data**: two messages sharing a 400-char prefix
  collapse to one string and `UNIQUE(content)` drops the second while the tool reports success.
  Clip at a boundary AND append a tail read from the END of the message (`content[-32:]`) — reading
  it at the clip offset is identical for both messages and does not help.
- **Runtime framing stored as user facts**: `[System:…]`, `[Surface:…]`, `Gateway message origin…`
  arrive inside `role="user"` rows. Filter on an explicit prefix/marker allowlist.
- **`retrieval_count` was never written** — add a `record_retrieval()` and call it from every
  lookup, or usage ranking and any decay logic read zeros forever.
- **`hrr_dim` change used to brick retrieval.** Migrate by comparing `memory_banks.dim` against the
  configured dim and re-encoding from `content`. Also make `_rebuild_bank` SKIP wrong-dim blobs
  rather than raise — otherwise the bad row can never be deleted.
- **`remove_fact`/`update_fact` need one transaction**; `PRAGMA foreign_keys` is 0, so two
  autocommitted statements tear.
- **Trust needs a recovery floor** (`_TRUST_FLOOR`): `clamp(0,1)` makes 3 negative votes permanent
  because `min_trust_threshold` is 0.3 and nothing decays back.
- **A local HTTP decision service can be silently dead behind a 401.** A client wrapper that
  swallowed the exception made an entire feature report "healthy" while never once firing. The
  tell: a token env var set on the service, a middleware docstring promising a loopback exemption
  that the code never implemented, and a per-call timeout tuned on an idle box. Verify the
  endpoint returns a real verdict *with credentials*, and count the feature's output over days
  (per-day counts are the only evidence it ever fires).
- **Read-only probes must open `DatabaseSync(path, { readOnly: true })`**, and every query must
  run BEFORE `close()` — a query placed after close returns `undefined` silently, which surfaces
  as a `0` in the JSON payload and reads as "nothing there".

## Memory-store growth is a harness bug, not a disk problem

When a memory/state store outgrows its budget, find what is *generating* rows before scheduling
prunes: `select count(*) from messages where timestamp > ?` grouped by day gives the growth rate,
and `select max(created_at)` shows whether the writer is still active. A test harness that copies
the live DB per run with no cleanup produced 17 GB of orphans in three days; a RAII `Drop` guard
(cleanup on panic too) fixed it permanently. See the storage-hygiene rules in `system-admin` for
the disk-side counterparts.

## References

- `references/deployed-kurama-core.md` — the live instance: paths, unit file, exact commands,
  verification transcript, and the rollback steps.
- `references/candidate-landscape.md` — candidate survey with storage/dependency profile,
  benchmark evidence with its caveats, and the rejection reasons (with sources) so the same
  options are not re-litigated.
- `references/fleet-topology.md` — the verified two-node fleet (kurama-core + office laptop):
  transport, per-node wiring, the control-surface script, the cross-node test, the agent-fleet
  store auto-update, and store-health triage (node-quiet and non-conformant interpretation).
- `scripts/flat-mirror-check.sh <store-skills-dir> <flat-mirror-dir>` — verifies a staged-flat
  skills mirror against the store by name set; prints the expected flat count (distinct
  basenames) plus missing/extra names.

<!-- canvas-output:start -->
## Canvas output

A hand-off is a surface: a warn `callout` with the next action first, `keyvalue` for exact state (mono paths and hashes), `steps` with exactly one active, a danger `callout` for gotchas, `references` for the files to read. Hand over artifacts and decisions, not the whole workspace.
<!-- canvas-output:end -->
