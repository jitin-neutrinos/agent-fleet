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

Repo `~/Work/projects/Smartslate/smartslate-orbit`: Rust core in `core/` (loco_rs + SQLx, Postgres row-level security) and a Next.js 16 web app in `web/`, public at orbit.jitinnair.com through the `jitinnair-personal` tunnel. The repo docs are the source of truth for plan and design; this skill carries only how to run, verify and not trip.

## When to Use

Any task in that repo: building a plan phase, running or restarting the stack, verifying a deploy, editing the plan docs.

## Read first, in this order

1. Newest `scratch/STATUS_S*.md` — what is verified, in flight, deferred.
2. `docs/AGENTIC.md` §6 (AI build order, acceptance check per phase) and `docs/PLATFORM-ADMIN.md` §6 + §10 (platform-admin build order and the consent items that gate it). PRD phase names are authoritative: Phase 3 is the AI layer; the frontend was PRD Phase 2 even where older chat or status text called it "phase 3".
3. `web/AGENTS.md` and `web/node_modules/next/dist/docs/` before touching web code (Next 16: `proxy.ts` replaces `middleware.ts`).
4. `docs/DESIGN.md` is law for UI: design tokens only, no raw hex.

Plan changes are written into those docs and committed on their own (`git -c user.name=Hermes -c user.email=hermes@kurama-core.local commit`). Build only what the docs name, after the user's go (operator gate).

## Run it

- **DB:** container `orbit-db` (Postgres 16, host port 54329): `docker exec orbit-db psql -U orbit -d orbit_dev -c "..."`. The dev pool role `orbit` is a superuser and bypasses RLS, so isolation checks must `SET LOCAL ROLE orbit_app` (see `core/tests/rls_isolation.rs`); a green dev run proves nothing about isolation.
- **Core:** from `core/`, launch with the terminal tool's `background=true` (a trailing `&` is rejected): `set -a && . ./.env && set +a && BINDING=127.0.0.1 DB_MAX_CONNECTIONS=8 ./target/debug/orbit_core-cli start >> <scratch>/core-server.log 2>&1`. Let that shell source `.env` itself — the tool masks passwords inside URLs you type, so an explicit `DATABASE_URL` arrives corrupted. Confirm with `ss -tlnp | grep :5150`.
- **Web:** `npx next build` then `npx next start -p <port>` for anything behind the public hostname; `next dev` only on a private port. `next.config.ts` proxies `/api` and `/content` to the core (`ORBIT_CORE_URL`, default 127.0.0.1:5150). Read the orbit ingress port from `~/.cloudflared/jitinnair-personal.yml`; ports 3000–3010 belong to the `coding-workspace` container and 3011 to astra-webui. Orbit's own ports: 3013 = prod `next start` behind the tunnel, 3012 = the build the E2E run targets.

## Review / status pass (no changes)

The recurring ask: review plan, status, front end and back end context and present findings without touching the tree. Order:

1. `git log --oneline -8` + `git status -sb` — the newest commits and whether the worktree is clean.
2. Newest `scratch/STATUS_S*.md` — the last verified state. **Any commit after it is unverified until a gate run says otherwise** (see pitfalls).
3. Plan: `docs/PRD.md` (scope + build order), then `docs/AGENTIC.md` §6 and `docs/PLATFORM-ADMIN.md` §6 for the phase in flight.
4. Front end: file-search `web/src` for the screen inventory, `wc -l` per page for weight, then read `web/src/lib/api.ts` + `queries.ts` — the whole API contract in ~300 lines.
5. Back end: `core/src/controllers/` per controller, `core/migration/src/` per migration, and read Cargo.toml for the real dep set (DEPS.md can be stale).
6. Live check: `ss -tlnp | grep -E ':(3012|3013|5150)'`, `ps aux | grep -E 'next (dev|start)|orbit_core'`, then a cache-busted `curl -s -o /dev/null -w "%{http_code}" "https://orbit.jitinnair.com/?cb=$(date +%s)"`.
7. Gap scan (below), then present findings as canvas cards. Make no edits.

### Gap scan — find what the plan named but the UI never built

Run these as `search_files` content searches, not by reading every file:

- For each function in `web/src/lib/api.ts`, search for its use in `web/src/app/`. A function with no caller is a backend-done / UI-missing gap.
- Same for `web/src/lib/queries.ts`: a hook defined but used by no page is the same gap one layer up.
- A component prop no caller passes (e.g. an optional `restricted` flag) is dead UI code, not a shipped feature.
- A value in a TypeScript union is not proof the UI offers it: check the `<SelectItem>` list for the option before believing a provider/setting is reachable.
- In core, an underscore-prefixed binding (`_citations`) is collected-then-dropped — the feature exists on paper only.
- A `docs/*.md` file referenced by a code comment (`web/WIRING.md`) may not exist; verify the referenced path exists (file search) before citing it.

## Gates (all green before reporting done)

- Core: `cargo test` in `core/` (RLS isolation + request tests).
- Web: `npx tsc --noEmit && npx eslint src` (zero errors, zero warnings), then `npx next build`.
- Design: `python3 scripts/check_tokens.py` and `python3 scripts/check_contrast.py`. A token change also updates the tables in `docs/DESIGN.md`; fix a contrast failure in the token, never by loosening the gate.
- Browser: an end-to-end run through the real path (browser → Next rewrite → core), both themes, 390 px with no horizontal overflow.
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
- Status and plan reports are Astra canvas cards, validated before emission (`structured-surface-emission`). Security and plan audits of this repo: `codebase-audit`; GLM provider behavior for the tutor and agent: `zai-glm-routing`.
