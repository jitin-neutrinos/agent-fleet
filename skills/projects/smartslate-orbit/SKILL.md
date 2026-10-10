---
name: smartslate-orbit
description: "Use when working on the Smartslate Orbit LMS repo."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [orbit, lms, rust, nextjs, runbook]
    related_skills: [cloudflare-edge-caching, codebase-audit, zai-glm-routing, structured-surface-emission]
---

# Smartslate Orbit (AI-native LMS) — runbook and pitfalls

Repo `~/Work/projects/Smartslate/smartslate-orbit`: Rust core in `core/` (loco_rs + SeaORM 2.0 raw SQL, Postgres row-level security) and a Next.js 16 web app in `web/`, public at orbit.jitinnair.com through the `jitinnair-personal` tunnel. The repo docs are the source of truth for plan and design; this skill carries only how to run, verify and not trip.

## When to Use

Any task in that repo: building a plan phase, running or restarting the stack, verifying a deploy, editing the plan docs.

## Read first, in this order

1. Newest `scratch/STATUS_S*.md` — what is verified, in flight, deferred.
2. `docs/AGENTIC.md` §6 (AI build order, acceptance check per phase) and `docs/PLATFORM-ADMIN.md` §6 + §10 (platform-admin build order and the consent items that gate it). PRD phase names are authoritative: Phase 3 is the AI layer; the frontend was PRD Phase 2 even where older chat or status text called it "phase 3". Phase plans live in `docs/PHASE4-PLAN.md`, `docs/PHASE5-PLAN.md` and `docs/MULTITENANT-PLAN.md`; each was approved by the user before any build.
3. `web/AGENTS.md` and `web/node_modules/next/dist/docs/` before touching web code (Next 16: `proxy.ts` replaces `middleware.ts`).
4. `docs/DESIGN.md` is law for UI: design tokens only, no raw hex.

Plan changes are written into those docs and committed on their own (`git -c user.name=Hermes -c user.email=hermes@kurama-core.local commit`). Build only what the docs name, after the user's go (operator gate).

## Run it

- **DB:** container `orbit-db` (Postgres 16, host port 54329): `docker exec orbit-db psql -U orbit -d orbit_dev -c "..."`. The dev pool role `orbit` is a superuser and bypasses RLS, so isolation checks must `SET LOCAL ROLE orbit_app` (see `core/tests/rls_isolation.rs`); a green dev run proves nothing about isolation.
- **Core:** from `core/`, launch with the terminal tool's `background=true` (a trailing `&` is rejected): `set -a && . ./.env && set +a && BINDING=127.0.0.1 DB_MAX_CONNECTIONS=8 ./target/debug/orbit_core-cli start >> <scratch>/core-server.log 2>&1`. Let that shell source `.env` itself — the tool masks passwords inside URLs you type, so an explicit `DATABASE_URL` arrives corrupted. Confirm with `ss -tlnp | grep :5150`. A second instance for live smoke while the main core keeps running takes `PORT=5151 BINDING=127.0.0.1` — `BINDING` is the host only, so `BINDING=127.0.0.1:5151` dies with "failed to lookup address information".
- **Web:** `npx next build` then `npx next start -p <port>` for anything behind the public hostname; `next dev` only on a private port. Deploy = copy the changed sources into the main checkout, swap the build (`cp -r <built>/.next web/.next`, keeping the old one as `.next.bak-<name>` for rollback), then `systemctl --user restart orbit-web.service` (enabled, Restart=always; since 2026-10-10 — the old bare `npm exec next start` died with its chat session and took the site down). `next start` serves the build it loaded at startup, so a source swap without a restart changes nothing. `next.config.ts` proxies `/api` and `/content` to the core (`ORBIT_CORE_URL`, default 127.0.0.1:5150). Read the orbit ingress port from `~/.cloudflared/jitinnair-personal.yml`; ports 3000–3010 belong to the `coding-workspace` container and 3011 to astra-webui. Orbit's own ports: 3013 = prod behind the tunnel, 3012 = the build the E2E run targets.
- **orbit-core.service is deliberately DISABLED:** enabling it while another session's bare core process holds 5150 makes it crash-loop (hit restart counter 594) — auto-migrate fails on the other session's uncommitted migration state (a migration file renamed after the DB applied it reads as "applied but missing"). Before enabling: nothing else on 5150 AND the migration table matches `core/migration/src/`.

## Review / status pass (no changes)

The recurring ask: review plan, status, front end and back end context and present findings without touching the tree. Order:

1. `git log --oneline -8` + `git status -sb` — the newest commits and whether the worktree is clean.
2. Newest `scratch/STATUS_S*.md` — the last verified state. **Any commit after it is unverified until a gate run says otherwise** (see pitfalls).
3. Plan: `docs/PRD.md` (scope + build order), then `docs/AGENTIC.md` §6 and `docs/PLATFORM-ADMIN.md` §6 for the phase in flight.
4. Front end: file-search `web/src` for the screen inventory, `wc -l` per page for weight, then read `web/src/lib/api.ts` + `queries.ts` — the whole API contract in ~300 lines.
5. Back end: `core/src/controllers/` per controller, `core/migration/src/` per migration, and read Cargo.toml for the real dep set (DEPS.md can be stale).
6. Live check: `ss -tlnp | grep -E ':(3012|3013|5150)'`, `ps aux | grep -E 'next (dev|start)|orbit_core'`, then a cache-busted `curl -s -o /dev/null -w "%{http_code}" "https://orbit.jitinnair.com/?cb=$(date +%s)"`.
7. Gap scan (below), then present findings as canvas cards. Make no edits.

Inventory counts come from the right source, or the report is wrong: tables = distinct `CREATE TABLE` names in `core/migration/src/*.rs` (33 at cf52fc4; `models/_entities` holds only 14 SeaORM entities), routes = `.add(` in `core/src/controllers/*.rs` (78). ARCHITECTURE.md's stack table is stale: the code has 0 `sqlx::query!` macros and ~143 raw-SQL calls through SeaORM, so never claim compile-time query checking. LTI is TOOL-only (`core/src/lti/mod.rs` header) — no platform role.

### Gap scan — find what the plan named but the UI never built

Run these as `search_files` content searches, not by reading every file:

- For each function in `web/src/lib/api.ts`, search for its use in `web/src/app/`. A function with no caller is a backend-done / UI-missing gap.
- Same for `web/src/lib/queries.ts`: a hook defined but used by no page is the same gap one layer up.
- A component prop no caller passes (e.g. an optional `restricted` flag) is dead UI code, not a shipped feature.
- A value in a TypeScript union is not proof the UI offers it: check the `<SelectItem>` list for the option before believing a provider/setting is reachable.
- In core, an underscore-prefixed binding (`_citations`) is collected-then-dropped — the feature exists on paper only.
- A `docs/*.md` file referenced by a code comment (`web/WIRING.md`) may not exist; verify the referenced path exists (file search) before citing it.

## Comparative audit against a large external OSS codebase (the "audit X vs ours" ask)

Recurring engagement: audit a big open-source project and compare it against Orbit; present findings, change nothing. The external repo is audited without ever entering our tree.

1. **Blobless clone into scratch, never into the repo:** `cd ~/.hermes/cache/scratch && mkdir -p <name>-audit && cd <name>-audit && git clone --filter=blob:none --no-checkout --depth 1 <url> repo`, then `git ls-tree -r --name-only HEAD > files.txt`. A 67k-file repo inventories in seconds and costs no blobs.
2. **Count subsystems from the file list, not by reading code:** `awk -F/` + `sort -u` over `files.txt` per plugin family; fetch one file only when a line count or class shape is needed (`curl -s https://raw.githubusercontent.com/<owner>/<repo>/<sha>/<path> | wc -l`). Pin the SHA first (`gh api repos/<o>/<r>/commits/main --jq .sha`) so line counts are reproducible.
3. **Walk the root tree before trusting a path.** The GitHub recursive `git/trees` API truncates (`truncated: true` once a repo passes ~56k entries), so a grep over it silently misses whole subsystems; the contents API 404s on paths a restructure moved — list the root tree (`gh api repos/<o>/<r>/git/trees/main --jq '.tree[]|select(.type=="tree")|.path'`) and walk from the top instead of guessing `/mod`, `/enrol`, `/auth`.
4. **Score both sides with the same kind of probe:** our numbers come from `wc -l`, the controller/route/model walk and `git log`, so every row in the comparison table is evidence-backed on both columns.
5. **One canvas card** (`codebase-audit` recipe): badges → verdict callout → kpi rows for each side → subsystem tables → the borrow/rebuild/skip decision table → a performance table → a danger callout naming what NOT to copy → steps (all `todo`) → references with real hrefs.
6. **Label the evidence tier inside the card.** Anything not measured on this machine is a cited number; a micro-benchmark is never an LMS-page latency claim — real page time is DB-bound, so the caveat goes in the same cell as the figure.
7. **Prove "no changes":** end with `git status -sb` matching session start and say so in the card.

Harvest decisions for Moodle specifically (schemas worth borrowing, what to skip): `references/moodle-comparison.md`.


## Gates (all green before reporting done)

- Core: `cargo test` in `core/` (RLS isolation + request tests) — against a throwaway DB, not orbit_dev (the suite wipes it; see pitfalls).
- Tenancy ratchet: `core/tests/tenancy_catalog.rs` enumerates every table dynamically — a new table without `org_id NOT NULL` + RLS enabled AND forced + ≥1 policy + an org-leading index fails the suite. Run it on a freshly migrated throwaway DB before claiming any migration done. **A delegated build that hand-patched the live DB to make its own run pass only fails on the fresh one:** after any agent-built wave, drop and recreate the throwaway DB, migrate, and run the ratchet before believing its report — a green run against a hand-patched database is not evidence.
- SQL ratchet: `python3 scripts/check_sql_interp.py` from repo root — exits 1 when the count of `format!`-built SQL grows past its baseline; new controller code binds parameters (`Statement::from_sql_and_values`). It is wired as the `sql-ratchet` job in `core/.github/workflows/ci.yaml` — a gate script nothing invokes is decoration; when adding a new gate, wire it in the same commit. The baseline is per-tree: waves landing on other sessions' uncommitted edits re-set the baseline to the tree's true count at merge, in the same commit, with the reason in the message.
- Users column lockdown: `orbit_app` may SELECT only `users (id, pid, email, name, email_verified_at, created_at, updated_at)` — scoped queries must not select secret columns (auth flows run on the owner pool, which is unaffected). The test asserts the EXACT set (every readable column positive, every secret column negative) — a one-column negative check lets a future over-grant of any other secret pass silently.
- Web: `npx tsc --noEmit && npx eslint src` (zero errors, zero warnings), then `npx next build`.
- Design: `python3 scripts/check_tokens.py` and `python3 scripts/check_contrast.py`. A token change also updates the tables in `docs/DESIGN.md`; fix a contrast failure in the token, never by loosening the gate.
- Browser: an end-to-end run through the real path (browser → Next rewrite → core), both themes, 390 px with no horizontal overflow. For marketing pages the bar is the reusable playwright-suite pattern (`~/Work/scratch/orbit-landing/landing-e2e.mjs`): section presence, ban scans, overflow, axe, both themes, plus a vision_analyze review of full-page crops — scroll the page first or reveal-on-scroll sections capture blank.
- **Frontend deploys are browser-verified, never curl-verified.** A curl 200 for the page HTML and a curl 200 for the JSON endpoint, checked separately, both pass while the page is dead in a browser: the crash is in the JS when the two meet. Before reporting any web deploy done, run the real path in a headless browser (playwright from `~/Work/projects/astra-webui/node_modules/playwright`) and assert on rendered content and zero `pageerror`s — pricing, approvals and settings each shipped "green" on curl evidence and broke on first click. Re-runnable walk: `scripts/browser-verify.cjs`; the endpoint shapes behind those crashes: `references/api-contract-shapes.md`.
- Public: after a deploy, verify the hostname with a cache-busted URL (`?cb=$(date +%s)`); see `cloudflare-edge-caching`.

## Frontend acceptance bar (every screen)

Wired to the real API through the `web/src/lib/queries.ts` hooks (never re-fetch); skeleton while loading, a real empty state, an error with retry; no stubs, TODOs, placeholder copy, disabled no-op buttons, `alert()` or emoji icons (lucide, `aria-hidden`); both themes. Prove wiring with a scan that every function in `web/src/lib/api.ts` is used by some screen.

## Pitfalls

- **Dev pool of 1 deadlocks the invite path:** it holds a scoped transaction and then takes a second connection, surfacing as 500 "Failed to acquire connection from pool". Keep `DB_MAX_CONNECTIONS` ≥ 2 (8 used); any handler that opens a second connection inside a scoped transaction needs the same.
- **`next build` under a running `next dev` overwrites `.next`** and kills HMR (`ERR_INVALID_HTTP_RESPONSE`, dead UI). Stop dev, `rm -rf .next`, restart.
- **`useSearchParams` needs a Suspense boundary** in Next 16 or `next build` fails prerendering that page: keep `page.tsx` a server wrapper (Suspense + metadata) and put the hook in a client child.
- **A new status code meets the client's global handlers:** `providers.tsx` logs the user out on any 401, so "more privilege needed" and "forbidden" states must be 403 with a machine-readable code.
- **The core can die during a long end-to-end run** (its log ends with `shutting down...`): check the port before chasing an app bug.
- **The public hostname must be served by a production build.** A dev server behind the tunnel serves HTML whose chunks vanish on restart, and the zone's catch-all cache keeps it for a year, so the page paints but never hydrates. See `cloudflare-edge-caching`.
- **Commits after the last STATUS file are unverified.** A commit message claiming a feature proves nothing about whether the UI exposes it or the gates ran: the newest phase-3 commits landed with no tsc/eslint/build/token/contrast pass recorded. Before trusting or reporting any recent commit as done, run the gates against HEAD, and grep the actual component before claiming an option is reachable.
- **Lost test password:** `POST /api/auth/forgot`, read `users.reset_token` from the DB, `POST /api/auth/reset`; save the new secret to a 0600 scratch file and print status codes only (stdout is logged). Probe each account with its own password before concluding auth is broken.
- **Worktree node_modules must be a real copy, not a symlink to the main checkout**: Turbopack panics ("Symlink node_modules could not be resolved") during `next build` (Next 16); `cp -a` it (762M) and leave it untracked.
- **Staging on main is shared state**: another session's files can sit in the index. `git add <only-my-paths>` then INSPECT `git diff --cached --name-only` BEFORE committing — one blind commit shipped 6 foreign files inside a login commit (caught, soft-reset, recommitted clean; their staged state restored after). Same applies to landing-page commits: stage only `web/src`, `web/next.config.ts`, `docs/DEPS.md`.
- **Entry flow (since commit 1158037)**: signup is REMOVED by design — /register 308s to /pricing and is the only on-ramp; accounts come from billing or invites. Never re-add register links or an api.register client call. The login page is the Polaris-style 50/50 split (`web/src/app/login/login-panel.tsx`, roles: admin/instructor/learner only; role copy lives in that file's ROLES map).
- **Login E2E harness**: `~/Work/scratch/orbit-login/login-e2e.mjs <base-url>` (3017 pre-deploy, public hostname post-deploy): themes, 390px overflow, wrong-password message, REAL QA sign-in from the 0600 cred file, /register redirect chain. 36 checks; the cargo-test DB-wipe gotcha below will kill the real-login check — reseed first (the worker left `seed-qa.mjs`).
- **cargo test truncates ANY DB it runs against — including the throwaway one:** the request-test suite wipes its target DB mid-arc, so seeded orgs and QA accounts vanish and a login that worked yesterday 401s today — it reads like an auth bug but it is the test run. The wipe does not spare `orbit_x_test`, so a live-smoke seed made before the final suite run is gone by smoke time: run the suite FIRST, then re-seed the QA org through the API (register → org → course → module → lesson → ULS → publish → AI config → invites with explicit roles) and log in fresh before probing; see `references/api-contract-shapes.md` for the seed shape.
- **A wrapped list endpoint breaks the page, not the API:** the core returns `json!({ "keys": rows })` for list endpoints (plans, keys, webhooks, deliveries, LTI deployments, platform orgs/audit, agent proposals/history) while `web/src/lib/api.ts` typed the same call as a bare array; `.map` on the wrapper object throws and the route dies with "page couldn't load" while both the backend and a curl of the JSON look healthy. When a canvas page crashes this way, audit EVERY list call in api.ts against its endpoint's actual shape and unwrap `(await request<{ k: T[] }>(...)).k` — the same mismatch class has hit pricing, approvals and settings; the full map is in `references/api-contract-shapes.md`.
- **Writes go through `Scope::exec()`, reads through `Scope::rows()`:** `rows()` wraps the SQL in `WITH t AS ({sql}) SELECT … FROM t`, so an INSERT/UPDATE without RETURNING sent through it dies at runtime with `WITH query "t" does not have a RETURNING clause` (500, invisible to the compiler). Route every mutation to `exec()`; only SELECTs and `INSERT … RETURNING` belong in `rows()`.
- **uuid columns bound from path strings fail at runtime, not compile time:** a `Path((String, String))` param bound directly into a uuid column gives `operator does not exist: uuid = text`; either parse to `Uuid` before binding or cast in SQL (`$3::uuid`). The read side mirrors it: `try_get::<String>` on a uuid column fails — select `id::text AS id`. `try_get::<i64>` on an int4 column fails and `unwrap_or(0)` swallows it, so prices render ₹0 and seat limits 0 with no error anywhere. Cast in SQL (`seat_limit::bigint AS seat_limit`) and type the read as i64; this has hit the plans table twice.
- **Multi-statement SQL goes through execute_unprepared, never execute_raw:** the extended protocol rejects `SET LOCAL ROLE ...; SET LOCAL ...` ("cannot insert multiple commands into a prepared statement"); `execute_unprepared` runs the same string fine. Per-transaction scope setup needs the unprepared call.
- **Deterministic doubles need clock-seeded ids and content-hashed event ids:** a fixture provider whose counter starts at 1 re-issues the same subscription id after every restart and two orgs collide on it; a webhook event id generated fresh per delivery defeats idempotency (a replay becomes a new event). Seed fixture counters from the clock; derive event ids from a hash of the signed body.
- **Brand assets live in the sibling constellation repo:** the swirl emblem (2484×2525 PNG), the full wordmark (640×92) and favicon.ico are in `~/Work/projects/Smartslate/smartslate-constellation/public/`; Orbit copies them to `web/public/brand/` and the favicon to `web/src/app/favicon.ico`. In the collapsed sidebar rail a 2484-px source stretches unless the img carries explicit width/height/maxWidth/maxHeight with object-contain and the container is justify-center.
- **Views run with their owner's rights.** The owner is the superuser `orbit`, so a plain view skips RLS entirely (probe 2026-10-10: table 1 row, view 10 rows across orgs). Never add a view without `WITH (security_invoker = true)`.
- **FK checks bypass RLS.** A scoped `orbit_app` txn can insert a row referencing another org's record it cannot see. Only composite FKs `(org_id, x_id) → parent (org_id, id)` stop it; plan v2.1 D3 retrofits the 14 org-blind ones. For a nullable composite FK use `ON DELETE SET NULL (col)` or it nulls `org_id` too.
- **UNIQUE treats NULLs as distinct** — `(org_id, user_id)` with a nullable user allows duplicate org rows; use `UNIQUE NULLS NOT DISTINCT` (PG16 here).
- **Index audits read the catalog, not migration greps:** UNIQUE constraints create indexes that `CREATE INDEX` greps miss. Query `pg_index` (`indkey[0]` = org_id attnum).
- **Prove DB claims with rolled-back probes:** `docker exec -i orbit-db psql -U orbit -d orbit_dev -At` with a `BEGIN … SET LOCAL ROLE orbit_app … ROLLBACK` heredoc; seed GUCs with `set_config(…, true)` before the role switch.
- **Code graph:** `graphify update . --no-cluster` builds `graphify-out/` LLM-free; it is excluded via `.git/info/exclude`.
- **`ORBIT_CORE_URL` is baked at `next build` time** (next.config.ts reads it during build; `next start` env is ignored by the rewrite): a start with a different env still proxies to the baked port and 500s with ECONNREFUSED 5150 in the log. Rebuild with the env set, or the dev default must actually own 5150.
- **Editing a validated canvas card on disk:** the patch tool's fuzzy match reflows single-line JSON and the write is refused ("candidate content fails .json syntax validation") — one bad edit and the file is untouched. Do a Python `json.load` → mutate → `json.dump` round-trip on the scratch file instead, then re-run `validate-canvas-spec.mjs` before emitting.
- **Run the suite against a throwaway DB:** create it with TWO separate psql `-c` calls (`DROP DATABASE IF EXISTS orbit_x_test`, then `CREATE DATABASE orbit_x_test` — combined in one call they fail: "DROP DATABASE cannot run inside a transaction block"). Read the URL from `.env` (`grep -oP 'DATABASE_URL=\K.*' | sed 's|/orbit_dev|/orbit_x_test|'`) and `export DATABASE_URL="$DBURL"` — never type the URL (the tool masks it mid-string) and never `export $(grep …)` (the value is not a valid identifier). Migrate with `./target/debug/orbit_core-cli db migrate` from `core/`, then run the suite.
- **Composite org-keys make org-sloppy test seeds fail — that is the FKs working, not a bug:** a fixture inserting rows whose parents were committed by a DIFFERENT test's orgs now violates the `(org_id, x)` FKs; filter seeds to the test's own orgs (`WHERE e.org_id IN (org_a, org_b)`) or join the parent per-org.
- **EXPLAIN assertions judge the main loop, not InitPlans:** a Seq Scan inside an `InitPlan`/`SubPlan` (constant lookup) is not the driving scan — parse plan indents and flag only main-loop scans. Write the checked queries the way the API does: an unordered `(SELECT id FROM t LIMIT 1)` seq-scans by design (use `ORDER BY id LIMIT 1` on the pkey or an org-leading predicate), and an UNLIMITED full-tenant listing legitimately seq-scans at scale — assert on the paginated shape the endpoint actually runs (`ORDER BY … LIMIT`), and for order-by keys make them index-leading (`ORDER BY org_id DESC, id DESC`, not `created_at` which no org index leads). **Every check must actually ride the index under test:** a check whose predicate/order keys don't lead with the migration's new columns passes even with the index dropped — EXPLAIN each check and confirm the new index's name appears in the plan before trusting the suite. Prefer checks with a decisive index win: when the planner sits within ~2% between Seq and Bitmap (small tenant slice of a big table), a minor-version cost tweak flips the plan and reds the CI without any regression.
- **A superseded failure can arrive after its fix:** a background test run dispatched before a fix reports the old failure long after the fix is committed. Before re-fixing or reverting, re-run the single failing test against the current tree — the log's binary mtime/test identity tells you which state it ran.
- **A stopped agy may not be stopped:** killing the `agy` wrapper pid leaves `agy.real` (separate pid) writing files — your next edit gets refused with "modified since read" while it keeps editing. `pgrep -af agy.real`, kill BOTH pids, re-read any file it owned before patching, and delete its scratch debris (`fix_*.sh`, `test_*.py`, stray `server.js`) before committing.
- **Independent review runs on a Hermes one-shot (glm-5.3, zai), not Claude Code** — same quota pool as builds, findings-only contract (no fixes, no commits; severity + file:line + one verdict), and it verifies schema claims against the live DB. It has caught two majors the orchestrator's own gate run missed (an unwired gate script; EXPLAIN checks passing without riding the new indexes).
- **When another session's agent owns the main tree, build the wave in a detached worktree** (`git worktree add --detach ../orbit-wt-<wave> <sha>`): another wave's edits trip the stale-read guard mid-patch, and shared files (migration lib.rs, controllers/mod.rs, api.ts) merge last, after the foreign wave lands. Full suite runs against a throwaway DB from the worktree; the node_modules copy gotcha above applies to any web build there.
- **Concurrent waves collide on migration numbers and on shared DBs:** two streams both claiming `m20261019_000014` leave a shared DB with an applied-but-missing migration file ("Migration file of version X is missing" on every migrate) — recover by copying the applied migration file into the tree or deleting its `seaql_migrations` row, then re-migrating. A foreign wave's `down()` may also drop constraints later waves depend on (H1 dropped `memberships UNIQUE (org_id, user_id)`, which groups' composite FK needs) — re-add the constraint before migrating. Verify with `db status`, never assume the dev DB shape.
- Status and plan reports are Astra canvas cards, validated before emission (`structured-surface-emission`). Security and plan audits of this repo: `codebase-audit`; GLM provider behavior for the tutor and agent: `zai-glm-routing`.
