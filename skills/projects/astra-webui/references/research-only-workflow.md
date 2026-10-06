# Research-only requests on the Astra surface (findings-first, no changes)

Recurring owner pattern: "research X, check what we already have, check what frameworks/projects exist on GitHub, present findings. Make no changes yet."

## The procedure, in order

1. **Inventory what EXISTS in-tree first** — the ASK includes "check what we already have". Grep the repo AND the adjacent codebase (`~/Work/projects/astra-webui` + `~/.hermes/hermes-agent`) for the capability. The desktop app, the gateway, and web routers usually already hold 60–80% of the answer (STT, TTS, mic recorder hooks, upload streams all existed before the voice-notes research started). Reading the sibling surface's implementation is the single highest-value recon step.
2. **Then the outside world**: `web_search` in `execute_code` (3–4 queries, parallel-friendly) on the named quadrants: plugins/SDKs, format/protocol specifics, reference implementations. Then `web_extract` the top repo pages (GitHub READMEs through `web_extract` give stars/maintenance/license/method tables directly).
3. **Write the findings into the repo** (`docs/<topic>-research-<yyyymmdd>.md`) — it becomes the implementation plan later and survives the session.
4. **Report in chat with the same structure**: what we already have → architecture options with a recommendation → external projects ranked by fit (license/maintenance) → Android/platform specifics → gap list (the actual TODO order) → build order in phases → explicit UNDECIDED items for the owner. Answer and stop: the "make no changes yet" clause means no code edits, no deployment, no fixes discovered along the way — even if you spot a bug, it goes in findings.
5. Close with the follow-up question(s) that unblock implementation (e.g. hold-to-talk vs tap, transcript-in-bubble or manual, which STT door). On an approval turn, those decisions become phase 1.

## Pitfalls

- **Do not implement anything while the ask was research-only.** The owner reads "present your findings" and "do not make changes yet" literally: shipping even a small fix violates the contract and mixes your report with drift.
- **Check the sibling repos before the internet**: Hermes itself (desktop `use-mic-recorder`, `tools/transcription_tools.py`, gateway `run_inbound.py`, `web_routers/audio.py`) carries the proven flows. "We already have X" is a first-class finding — the build plan can be "port it", which beats a fresh integration.
- **Verify every external claim live**: extract the README (stars, last push, license, Capacitor major compatibility) — a plugin pinned to a different Capacitor major is unusable; an unmaintained repo is a finding, not a candidate.
- **Capacitor plugin compat is majored**: plugin v8 works only with Capacitor 8.x; check the repo's `package.json` / `npx cap` version before recommending, and note that any native plugin requires an APK rebuild + redeploy (web-only JS changes reach the device without one, since the APK loads the live site).
- **Android half of the stack is invisible on the server**: check `android/app/src/main/AndroidManifest.xml` permissions and `MainActivity.kt` overrides (e.g. `onPermissionRequest` for WebView getUserMedia) — the web research alone misses that the permission is missing and needs an APK.
- Present the UNDECIDED list rather than guessing: these are owner-judgement items (UX affordances), and a wrong guess costs a full implement-and-revert round.
