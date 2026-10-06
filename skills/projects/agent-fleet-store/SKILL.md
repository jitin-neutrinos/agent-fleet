---
name: agent-fleet-store
description: "Use when touching agent-fleet installers or repo visibility."
version: 1.0.0
author: notjitin
license: MIT
metadata:
  hermes:
    tags: [agent-fleet, installer, powershell, github, sync]
    related_skills: [kurama-work-projects, ctrader-stack]
---

# agent-fleet store on kurama-core

## When to Use

Load for ANY work on the agent-fleet store: serving/publishing an installer
(bash install.sh or windows install.ps1), changing the fleet repo's GitHub
visibility, wiring a new public file into the serving chain, or debugging a
401/unreachable one-liner.

Skill fleet + installer hosting. The store is repo `~/Work/infra/agent-fleet`
→ GitHub `jitin-neutrinos/agent-fleet` (public, single squash baseline;
full pre-baseline history preserved privately at `jitin-neutrinos/agent-fleet-history`).

## Serving chain — know before touching anything

- `health/status-server.py` + systemd user unit `agent-fleet-www.service`
  (127.0.0.1:8003); public only via the cloudflared tunnel `harness.jitinnair.com`.
- Served public files come from `~/scratch/agent-fleet-www/` — a **copy**, not
  the repo. Edit in repo → `cp` to that dir + write `<file>.sha256` → restart
  the unit. `PUBLIC_FILES` in status-server.py decides which routes answer
  publicly (install.sh, install.ps1 + their .sha256).
- `health/fleet-health.sh` three-way hash chain: repo sha == www sha == sha of a
  curl through the public URL. Every newly served file MUST get the same chain
  wired in, or it drifts silently.
- Catalog one-liners live in `catalog/build-inventory.py` (`STORE_INSTALL`,
  `STORE_INSTALL_WIN`); the sync script restarts the unit (6h timer). Restart by
  hand when you need it now: `systemctl --user restart agent-fleet-www.service`.

## Ship a public installer (or add a second one)

1. Build parity: the .ps1 mirrors install.sh's legs minus what cannot work on
   windows (see references/powershell-51-porting.md for port rules).
2. Copy to `~/scratch/agent-fleet-www/` + checksum in the SAME pass.
3. Same-pass wiring: `PUBLIC_FILES` entry, sync-from-desktop.sh mirror block, a
   fleet-health check, catalog `build-inventory.py` listing.
4. Verify END-TO-END through the tunnel, never just the socket:
   `curl -fsS https://harness.jitinnair.com/install.ps1 -o t && sha256sum t`
   vs the repo sha; parse the **served** bytes in real PowerShell (headless probe
   in the reference) — the bytes the laptop receives are the only artifact that
   matters.

## Repo visibility (public flip procedure)

Order matters; each step earns its place:
1. **Gate-scan first**, before any visibility change: inventory every
   vendored/licensed path (`git ls-files`; `grep -rE 'license: (Proprietary|Commercial)' --include=SKILL.md`).
2. Back up FULL history to a fresh PRIVATE repo (`gh repo create <x>-history
   --private && git push <backup> main --tags`) — this is what makes squashing safe.
3. Strip gated content and add matching `--exclude` rules to sync-from-desktop.sh
   IN THE SAME COMMIT: the 6h rsync timer silently re-commits anything not
   excluded at the rsync level.
4. Squash: `git checkout --orphan public-main && git add -A && git commit ...`;
   `git branch -M public-main main && git push -f origin main`; then LOCALLY
   `git reflog expire --expire=now --all && git gc --prune=now --aggressive` so
   dead history cannot resurface on a later push.
5. Flip: `gh repo edit <repo> --visibility public
   --accept-visibility-change-consequences`, then verify credential-free:
   `git ls-remote https://github.com/<org>/<repo>.git HEAD` + an anonymous fetch
   of the public artifact.

A 401 on a hosted one-liner is usually the GIT endpoint, not the HTTP server —
check repo visibility before debugging the store.

## Standing rules

- Fresh-machine failures (.ps1 on a laptop, anonymous run): the user's default
  is make the endpoint public — never require credentials for delivery.
- The installer's first real action (the git step) must be verified reachable
  WITHOUT any stored credential; test as the anonymous receiver.
- MCP copy row logic mirrors claude.list: env-gated rows, MACHINE_LOCAL rows,
  127.0.0.1 http rows and unix-abs binaries are SKIP on windows, by design.
- Per-harness discovery contracts (claude depth-1, agy flat, opencode recursive,
  hermes categorised) are part of the installer legs.

references/powershell-51-porting.md — headless probe recipe + the 5.1 traps.
