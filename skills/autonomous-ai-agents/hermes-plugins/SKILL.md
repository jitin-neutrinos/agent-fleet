---
name: hermes-plugins
description: "Use when installing or troubleshooting Hermes Agent plugins."
tags: [hermes, plugins, install]
---

# Hermes Plugins

How to install and enable Hermes Agent plugins. For the broader Hermes surface, load the `hermes-agent` skill first.

## Install sources — what `hermes plugins install <source>` accepts

- `owner/repo` — GitHub shorthand (optionally `owner/repo/path/to/plugin` for a subdir)
- Full git URL — `https://...`, `git@...`, `ssh://...`, or `file://...`
- Bare community-index name (e.g. `hermes-media-studio`)
- `--ref <40-char-sha>` pins an immutable commit

## Pitfall: local filesystem paths are NOT install sources

`hermes plugins install /home/me/Downloads/my-plugin/` does NOT work. A leading-slash path is
split on `/` and interpreted as `owner/repo` shorthand — `/home/notjitin/Downloads/x` becomes a
git clone of `https://github.com/home/notjitin.git`, which fails with
`could not read Username for 'https://github.com': terminal prompts disabled`.
The cryptic git credential error means "the URL was mangled from a bad identifier", not a real auth problem.

Fixes for a plugin that lives on disk:

1. **Git repo on disk** — use the file scheme (prints an expected insecure/local-scheme warning):
   ```bash
   hermes plugins install "file:///absolute/path/to/my-plugin"
   ```
2. **Plain directory (works even without .git)** — copy into discovery and enable:
   ```bash
   cp -r /path/to/my-plugin ~/.hermes/plugins/
   hermes plugins enable <name-from-plugin.yaml>
   ```
   The copy must carry `plugin.yaml` AND `__init__.py` — a bare-script hand-copy is the
   classic way a hook plugin ends up dead-on-arrival (see next section).

Either way the plugin is DISABLED by default — `install` prompts `Enable 'name' now? [y/N]`
(default no); `--enable` / `--no-enable` skip the prompt. Restart Hermes afterward and verify
with `hermes plugins list`.

## Wiring a hook plugin: manifest + register(), both required

A directory plugin is two files doing two different jobs:

- `plugin.yaml` — makes DISCOVERY see it. Discovery reads `<name>/plugin.yaml` (or `.yml`)
  under `~/.hermes/plugins/`; a manifest-less directory is treated as a category container,
  recursed once, and skipped at the depth cap. An `__init__.py` alone is never a plugin.
  Declare hooks under `provides_hooks:` (legacy `hooks:` still parses).
- `register(ctx)` in `__init__.py` — makes the hook RUN. Defining a `VALID_HOOKS` function
  (e.g. `pre_gateway_dispatch(event, ...)`) without
  `def register(ctx): ctx.register_hook("pre_gateway_dispatch", fn)` binds nothing; the
  manifest documents, only register() wires. Discovery and registration happen at process
  boot, so a newly laid plugin fires only after the long-running Hermes process (the gateway)
  picks it up — by restart, or faster via hot activation (next section). Boot-time activation
  can silently skip a just-enabled plugin; either path, verify firing on real traffic after.

Never wire a hook plugin by hand-copying files: the copy is where the manifest or the
`register()` gets lost, and every failure in this class is SILENT — all hooks fail open, so
there is no error line anywhere. Carry the full payload plus the enable step
(`plugins.enabled` in config.yaml; write it through `hermes_cli.config.atomic_config_write` to
preserve comments) in the owning project's installer, so a rerun reproduces the whole contract.

## Proving a plugin actually fires

Enabled-in-config + files-on-disk proves nothing. Three checks, strongest first:

1. **Discovery**: run Hermes' own discovery inside its checkout/venv —
   `from hermes_cli.plugins_discovery import collect_directory_manifests` — and require the
   plugin name in the result. A plugin missing manifest or register() is invisible here while
   looking fully installed.
2. **Firing evidence**: a per-message plugin writes something (cache file, audit log). Check
   that file's mtime against days of known live traffic: a timestamp that stopped days ago
   dates the death to the last process restart, and logs hold no error because every stage
   fails open.
3. **End-to-end**: import the plugin file, call `register()` against a stub ctx, invoke the
   registered function with a fake event, assert the documented return shape.

If one hand-wired plugin is missing its contract, audit every plugin enabled in the same
generation — the same hand-copy that dropped one manifest dropped others. Also reconcile the
cycle both ways: a stale `plugins.enabled` entry with no plugin behind it is inert, and a real
plugin missing from the list never loads.

## Loading a plugin without restarting (hot activation)

Run in the gateway's own venv from `~`:
`from hermes_cli.plugins_activation import activate_plugin_now; activate_plugin_now("name")`.
This force-redisCOVERS and attaches the plugin to the LIVE gateway — the result names the
attached hooks under `gateway_transforms`, the PID stays the same, and no chat blips. It is
the fast path for a newly enabled plugin AND the repair for a boot-time miss: after any
restart, check the per-message artifact's mtime (cache/log) against live traffic — silence
after a restart means boot activation skipped it, and re-running activate_plugin_now re-arms
it with zero downtime. Restart remains the coarse fallback. Confirm with a real message, not
just the activation result.

If the boot-time miss reproduces on every restart, automate the re-arm instead of repeating
it by hand: a user-level `Type=oneshot` unit that runs the activation snippet (with retries
and fail-open exit 0), plus a `Wants=<unit>` drop-in (`hermes-gateway.service.d/*.conf`) so
every gateway (re)start pulls it ~1 s after boot. Lay both from the plugin's installer so a
fresh machine gets the automation too; log each re-arm to an audit file. `hermes plugins enable <name>` also hot-reloads the running
gateway itself (the enable output says so) — a newly enabled hook plugin is usually live
immediately; still verify firing on real traffic.

## Restarting the gateway you are talking through

`systemctl --user restart hermes-gateway.service` kills your own chat session if run mid-turn.
Arm it detached and let the turn finish: `systemd-run --user --unit=<name> --on-active=120 sh -c
'systemctl --user restart hermes-gateway.service'`. Tell the user the blip is coming, then
deliver the report BEFORE the timer fires.

## Gating (pre/post) plugins: the contract and how to test one

- `pre_tool_call(tool_name, args, task_id)` returning `{"action": "approve", "message": ...,
  "rule_key": ...}` escalates the call to the user (HITL); `{"action": "block", "message": ...}`
  denies it outright (the slopguard/laya-guardrails shape); returning None passes. `post_tool_call`
  sees the result and can log or note, but cannot block — enforcement belongs in pre. The deny
  shape is HARNESS-specific outside Hermes: Claude Code's PreToolUse wants
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
  "permissionDecisionReason": ...}}` on stdout — grep a working sibling gate on that harness
  before inventing a payload, and don't reuse the Hermes dict across harnesses.
- Fail-open by default (a broken guard must never block work), EXCEPT the one narrow
  irreversible action the guard exists for — that layer fails closed. Name the exception in the
  module docstring so the next editor does not 'fix' it back to fail-open.
- Derive a validator's expectations from the LIVE healthy file, never from what the file
  'should' contain: a sentinel key the real healthy state legitimately lacks (e.g. a value
  that lives in `.env`) false-positives on every call and turns the guard into a
  restore-over-healthy loop within minutes of enable. Pin the exact false-positive as a
  selfcheck case so a future edit cannot reintroduce it.
- Sandbox-test by re-pointing module constants (HOME/STATE_DIR/LOG_PATH) at a scratch home and
  calling the hook functions with synthetic args; keep one assert-based selfcheck next to the
  plugin (no framework). Reference build: `~/.hermes/plugins/config-sentinel` (snapshot →
  sentinel key-check → atomic restore → restore-loop escalation), with its Claude Code twin
  (`claude_hook.py`) wired in `~/.claude/settings.json` for the same guard on that harness.

## Other notes

- Plugins are discovered from `~/.hermes/plugins/` (user), `<repo>/plugins/` (bundled),
  `./.hermes/plugins/` (project; needs `HERMES_ENABLE_PROJECT_PLUGINS=true`), and pip entry points.
- A plugin needs a `plugin.yaml` manifest AND a `register(ctx)` in `__init__.py` that calls
  `ctx.register_hook()` for each hook; `requires_env:` entries are prompted at install time.
- Every install/update runs a static security scan before activation; capability declarations
  (`capabilities:` in plugin.yaml) trigger a one-time consent prompt.
- Debug a local plugin with `hermes plugins doctor <name|dir>` — one shot over discovery, manifest parsing, import and register(), reporting the registration count (`registrations: 0 tool(s), N hook(s)`). ALWAYS pass the plugin name: bare `hermes plugins doctor` targets the CWD and errors confusingly from a random repo. Doctor proves the contract is wired; whether the hook FIRES still needs the proof ladder above.
- Docs page: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
  (note: `web_extract` on this page may return empty — fall back to `curl -sL` + regex HTML strip).
- Source of truth for accepted identifiers: `_resolve_git_url` in `hermes_cli/plugins_cmd.py`.
