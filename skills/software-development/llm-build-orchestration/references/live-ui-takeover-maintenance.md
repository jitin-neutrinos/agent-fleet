# Maintaining a live-product takeover against an upstream that updates (Astra pattern)

For UI takeovers delivered via a host's official extension surfaces (plugins + theme),
where the host releases updates on its own schedule and the owner demands their
customizations survive every update.

## Architecture invariants
- Zero edits to the host checkout — the takeover lives entirely in user-space plugin
  dirs + theme files + config keys. Verify with `git -C <host-checkout> status --porcelain`
  empty at every gate.
- One core design-system file (IIFE, module pattern, no bundler) loaded by every
  per-page stub; stubs gate on a REAL capability check (`typeof core.registerPage ===
  'function'`), never on a bare global existing — another script can squat the global
  name and every page silently no-ops.
- Feature-detect the host SDK via its actual export (`window.__HERMES_PLUGIN_SDK__`),
  not an imagined bare global; an SDK gate written against the wrong name no-ops
  silently and looks identical to "SDK missing".
- Every page's fetch layer treats auth-expiry as a UI event (redirect to login or an
  expired-session card) — never leave a loading skeleton up forever on 401.
- Streaming UI state must clear on BOTH completion paths: the completion message AND
  socket close. A websocket that dies mid-stream never delivers its "message.complete",
  so any flag keyed only on that message (Stop button, caret, disabled composer) sticks
  forever after a restart. Clear streaming state in `ws.onclose` (before the reconnect
  branch) and pair it with capped auto-reconnect that resumes the same session; verify
  by restarting the service mid-generation, not by simulating a clean close.

## Update-trigger pipeline (owner's contract)
1. Detector script snapshots the relevant upstream surface (not just version): git
   HEAD vs origin/main over the dirs that define the extension surface — for the
   Hermes dashboard that is `web/`, `hermes_cli/web_routers/`, `web_server*`,
   `dashboard_auth/`, `pty_bridge.py`, `tui_gateway/`, `apps/shared/`.
2. Classify the diff, not just detect it:
   - ADDITIVE (new pages/endpoints/slots) → port agent may proceed, additive-only,
     timestamped backups of every owned file BEFORE edits.
   - BREAKING (plugin-SDK contract files modified; routes removed/renamed) → the
     agent makes ZERO changes and escalates to the owner on Telegram; nothing moves
     until the owner decides. Unit-test the classifier with a table of file/status →
   expected-class cases kept next to the script.
3. NEVER-OVERWRITE is enforced in TWO layers: the pending-diff the agent reads carries
   the allowed globs + rules, AND the scheduled agent's standing prompt repeats them —
   if a required change would touch a customized file, stop and escalate.
4. Post-port gate: plugin rescan (POST; GET returns 405) with a cookie session, bundle
   serves, eval harness 0 FAIL, positive browser page-load assert per touched page,
   report file written, THEN refresh the baseline snapshot (`--commit`). A FAIL at any
   step restores backups and reports NO-PORT with reasons.
5. Run the trigger on a cron (cheap fast model) that delivers to the owner's messenger;
   pin `--model/--provider` on the job so global default-model drift cannot silently
   change (or skip) the agent.

## Ops rules that saved this pipeline
- Multi-valued config keys (e.g. `plugins.enabled`) are typed: writing them via
  `hermes config set k a,b,c` yields a STRING where the loader wants a LIST — a string
  silently enables zero user plugins while the service stays green. Rewrite the whole
  list as a YAML list in the config file (anchor on the owning section; the key name
  recurs in unrelated sections), then verify it parses as list + count, restart, and
  assert the plugins actually load via the discovery API before declaring victory.
- Service restarts under systemd self-recover within one restart cycle — check
  `systemctl is-active` + curl before intervening; but they invalidate browser
  sessions, which users experience as a permanently-loading page. Treat redirect-on-
  401 as a product requirement, not polish.
- Some host routes are server-owned (e.g. FastAPI Swagger at /docs) — an SPA route
  override can never catch direct loads of those; mark them stock-fallback in the
  coverage map honestly instead of shipping an override that works only for in-app
  navigation.
- Keep an owner-decision log inside the coverage map (mode + note) so future port
  agents read the decisions instead of re-asking.