---
name: hermes-web-ui-qa
description: "Hermes web UI QA and update survival."
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, web-ui, qa, update, survival, ux, glm, flash, theme, skin]
    homepage: null
    related_skills: [hermes-agent, neutrinos-web, neutrinos-brand-core]
---

# Hermes Web UI QA & Update Survival

## always-on rules (SKILL.md itself)

### 1. Web UI build stamp tracking
The file `.hermes/web-ui-build-stamp.json` records the last web UI build. Before any Hermes update that touches the web UI, check this stamp. If the hash changed from your last known good value, your custom modifications may have been overwritten.

### 2. Theme/skin persistence through updates
Custom UX is composed of two parts that both survive Hermes updates. Dashboard theme (`~/.hermes/dashboard-themes/astra.yaml`) defines color palette, typography, layout, and component styles. Skin (`~/.hermes/skins/astra.yaml`) defines UI surface colors. Both persist across Hermes updates — never delete or rename them after an update without backing up first. Most of the custom UI, however, is plugin-based (`~/.hermes/plugins/astra-brand`, `astra-page-*`, `astra-login`); the theme/skin files only paint the stock chrome and the sign-in page. The maintenance procedure, hard rules and QA recipes for that plugin surface live in the **astra-webui** skill (its `references/qa-auth.md`, `references/contract-probes.md` — under `~/.hermes/skills/projects/astra-webui/`, not this skill's directory) — read it before touching anything here.

### 3. Named Cloudflare tunnel persistence
The Hermes MCP setup uses a named Cloudflare tunnel that survives reboots. Tunnel endpoint: `https://mcp.glitchzerolabs.com/mcp`. Never recreate the tunnel with a quick tunnel URL — always use the named tunnel. If the tunnel URL changes, update the config and restart the service.

### 4. Update survival pattern
When a new Hermes web UI version is released: 1. Backup `~/.hermes/web-ui-build-stamp.json`, `~/.hermes/dashboard-themes/astra.yaml`, `~/.hermes/skins/astra.yaml`, and the `~/.hermes/plugins/astra-*` dirs. 2. Update Hermes via `nobara-sync`. 3. Check the new `web-ui-build-stamp.json` contentHash. 4. Merge any customizations. 5. Run the acceptance gate — `python3 ~/Work/astra/scratch/eval_astra.py` must print `24 checks, 0 FAIL`; a FAIL means a plugin/theme/coverage file moved, not that the UI is fine. 6. Leave upstream web-UI drift to the `astra-auto-port` cron (6h): it prints ESCALATE instead of porting when a contract file changed — never hand-port what it already watches. 7. Verify the astra.jitinnair.com MCP endpoint still resolves.

### 5. UI health monitoring (confirm a command exists before wiring it)
Never write a UI-diff or eval job from a remembered command line — confirm the subcommand exists (`hermes mcp --help`, `hermes cron --help`) before it goes into a cron entry, or the job fails silently every run. The monitoring that is actually in place: the `astra-auto-port` cron (every 6h, deliver=telegram) for upstream web-UI drift, plus `python3 ~/Work/astra/scratch/eval_astra.py` (24 checks, 0 FAIL) as the on-demand health gate — details in the astra-webui skill.

### 6. astra.jitinnair.com MCP stability
The astra.jitinnair.com endpoint uses the named Cloudflare tunnel `mcp.glitchzerolabs.com`, which survives reboots and Hermes updates. If it ever breaks, restore via: `systemctl --user restart neutrinos-mcp-tunnel`.

## pitfalls (imperative rules + why)

### Pitfall 1: Using quick Cloudflare tunnels instead of named tunnels
- **Rule**: Never use `cloudflared tunnel run <name>` without the `--name` flag for persistent MCP.
- **Why**: Quick tunnels issue a random subdomain per run. URL changes on every restart/crash/reboot, breaking MCP client configs. Named tunnels have a permanent URL.

### Pitfall 2: Deleting dashboard-themes or skins after a Hermes update
- **Rule**: Never remove `~/.hermes/dashboard-themes/astra.yaml` or `~/.hermes/skins/astra.yaml` after updating Hermes.
- **Why**: These files contain your custom UX theme. Removing them resets the UI to default, losing your design. Always back up before updating, and merge new defaults rather than replacing.

### Pitfall 3: Forgetting to check the build stamp after a Hermes update
- **Rule**: After any Hermes update that touches the web UI, always run `cat ~/.hermes/web-ui-build-stamp.json`.
- **Why**: The contentHash tells you if the UI was rebuilt. If the hash changed from your records, your custom modifications may have been overwritten — you need to re-apply your theme/skin customizations on top of the new baseline.

### Pitfall 4: Configuring glm 5.3 eval job without proper delivery setup
- **Rule**: If using a cron job for glm 5.3 UI diff checks, always set `deliver: telegram` and ensure the Telegram bot is connected.
- **Why**: The job outputs a diff report; without delivery configured, the report is written to `/tmp/ui-diff-report.md` but never seen.

## troubleshooting

### "Agent backend busy (503)" on astra.jitinnair.com
Not an update-stamp problem and rarely real backend load: the UI maps ANY 503 from the astra proxy to that string, and the usual cause is the proxy's login to the Hermes dashboard failing (`dashboard.basic_auth` lost from `~/.hermes/config.yaml` → provider unregistered → shared 127.0.0.1 rate-limit bucket saturates). Full chain — reproduce locally, read the 503 body, check config size (~22KB healthy, <1KB stub), restore newest pre-collapse `config.yaml.good.*`, restart `hermes-dashboard.service` — plus the red herrings: `references/astra-outage-triage.md`. (The astra-webui skill's Pitfalls carries the same lesson; that SKILL.md is currently over the size limit, so this file is the readable home.)

### Web UI appears broken after Hermes update
1. Check `~/.hermes/web-ui-build-stamp.json` - if contentHash changed, the UI was rebuilt.
2. Verify `~/.hermes/dashboard-themes/astra.yaml` still exists and has your customizations.
3. Verify `~/.hermes/skins/astra.yaml` still exists and has your customizations.
4. Run `systemctl --user restart neutrinos-mcp-tunnel` to ensure the MCP tunnel is still active.
5. If the UI is truly broken, restore from your last backup of the three key files.

### Tunnel URL changed unexpectedly
1. Check if a quick (unnamed) tunnel was inadvertently created.
2. Recreate the named tunnel: `cloudflared tunnel create neutrinos-mcp` then `cloudflared tunnel route dns --bgp <name> mcp.glitchzerolabs.com`
3. Update `~/.hermes/profiles/desktop/config.yaml` to point to the new permanent URL.
4. Restart the tunnel service.

### glm 5.3 diff report shows unexpected changes
1. Verify the build stamp hash matches your last known good value.
2. Check if a legitimate Hermes update introduced new UI pages/features.
3. If your theme/skin needs updating, edit `~/.hermes/dashboard-themes/astra.yaml` and/or `~/.hermes/skins/astra.yaml` rather than replacing them entirely.

## verification

After following any update survival procedure, verify:
1. `cat ~/.hermes/web-ui-build-stamp.json` shows a hash (any hash means the UI rebuilt successfully)
2. `ls -la ~/.hermes/dashboard-themes/astra.yaml ~/.hermes/skins/astra.yaml` both files exist and are non-empty
3. `systemctl --user status neutrinos-mcp-tunnel` shows the tunnel is active
4. `hermes mcp list` shows neutrinos-docs pointing to `https://mcp.glitchzerolabs.com/mcp`
5. `python3 ~/Work/astra/scratch/eval_astra.py` prints `24 checks, 0 FAIL` (the acceptance gate after any update).

---

*This skill covers Hermes web UI QA and update survival for the plugin-based Astra surface. Always verify the current state of the `.hermes/` files, and run the harness, before and after any Hermes update.*

<!-- canvas-output:start -->
## Canvas output

A report is a card with `"page":"a4"`, so it renders as the page it exports as: `badges` for state, `kpi` for what changed, `steps` or `timeline` with done/active/todo/fail, `progress` for coverage or budget, `checklist` for shipped vs deferred, one `callout` for what needs attention. Failures sit in the same card as successes.
<!-- canvas-output:end -->
