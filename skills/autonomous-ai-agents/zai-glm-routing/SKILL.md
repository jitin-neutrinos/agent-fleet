---
name: zai-glm-routing
description: "Use when changing Hermes model routing or z.ai GLM config, or when calling the z.ai GLM API directly (direct API pattern, art/structured generation)."
version: 1.1.0
---

# z.ai GLM smart routing on kurama-core (set up 2026-09-06)

## Current routing
- **Daily default:** `glm-5.3-flash` via provider `zai` (model.default in config.yaml)
- **Deep lane** (research/coding/brainstorm/reasoning): MoA preset `deep` —
  reference: glm-5.3-flash @ reasoning_effort low; aggregator: glm-5.3 @ reasoning_effort high
  - Select: `/model deep --provider moa` (session) or `/moa <prompt>` (one-shot)
- **auxiliary.vision + auxiliary.compression:** pinned `zai`/`glm-5.3-flash`.
  GLM-5.3 is TEXT-ONLY — vision must never route to it.
- **delegation:** intentionally unpinned — children inherit the parent's model,
  so Flash sessions spawn Flash workers and deep sessions spawn 5.3 workers.

## z.ai GLM quirks (Hermes-specific)
- GLM-5.2/5.3 ALWAYS think. `thinking: disabled` / `/reasoning none` → HTTP 400
  code 1210 on every turn. Never disable reasoning; use `low` as the floor.
  (hermes-agent issue #96373, open as of 2026-09)
- Flash is natively multimodal; GLM-5.3 is not.
- Flash generation ~49 tok/s vs 5.3 ~85 tok/s — 5.3 is FASTER on long outputs.
- Verified model IDs on api.z.ai: `glm-5.3`, `glm-5.3-flash`.

## Rate-limit & concurrency (learned Sep 2026)
- Z.ai API enforces hard per-minute caps on concurrent requests regardless of subscription tier — the $80 coding-pro plan gains NO extra concurrency headroom (verified live: a single test call also returned HTTP 429 while 12 workers ran; subscriptions raise quotas, not the concurrency cap).
- Empirical: 12 parallel GLM-5.3 calls → HTTP 429 after ~3 batches/10min.
- Effective parallelism: 1–2 concurrent calls; more workers queue rather than accelerate.
- Do NOT rely on adding more `vc_worker.py` instances to beat the limit — throughput caps at ~3 batches/10min observed.
- Engine switch is the proven escape: when GLM rate-limits stall a batch job, kill the GLM workers (progress is safe — resume-safe batch files on disk), then relaunch the same workers under agy/Gemini. Measured on the VC campaign: GLM 12-worker ≈ 3 batches/10min vs agy-Gemini 6-worker ≈ 11 batches/10min (~3.5×).
- agy CLI pitfalls: `--print` takes the prompt as `--print="..."` (a separate `--print "..." --print-timeout X` makes X the prompt and drops the real one); model ids come from `agy models` (e.g. `gemini-3.1-pro-high`, NOT `glm-5.3`); headless runs need `--dangerously-skip-permissions` or every tool call is auto-denied.
- Monitor long batch queues with ONE tracked background progress counter (`sleep 540; echo count`, notify=true) instead of repeated foreground sleeps — foreground `sleep` calls hit the 420s tool cap and waste a turn each.
- Audit §4.1 recommended: measure actual rate-limit before scaling workers.

## Direct GLM API calls (bypassing harnesses)
- Key: `~/.config/neutrinos-mcp/zai_key` (or `GLM_API_KEY` in `~/.hermes/.env` — parse it inside the script, never echo it); endpoint: `https://api.z.ai/api/coding/paas/v4/chat/completions` — the CODING endpoint only.
- Verify health before blaming config: curl the completions endpoint directly (expect 200). OpenCode `Unexpected server error` with a healthy direct API = OpenCode↔Z.ai integration issue — route the task to a delegate instead of debugging OpenCode.
- **Structured/ASCII generation:** `thinking: {"type":"disabled"}` works on direct API calls (harness calls 400 on it, API accepts it). Set `max_tokens` ≥ 8000 — GLM 5.3 burns 6k–27k tokens of `reasoning_content` before emitting content; small caps return EMPTY content with long reasoning. A 2-pass refine (generate, then cleanup-instruction pass) works, but each pass needs the big cap.
- Bitmap→ASCII tracing: convert the source image with PIL to a 2:1-aspect char grid first (terminal chars ~1:2 aspect), threshold on luminance with the threshold set well below the image's measured mean luminance (default thresholds reject dark brand logos), then have GLM restyle the grid rather than draw freehand. But on solid-color logos (e.g. flat brand blue), skip GLM for the final art: a deterministic PIL crop-to-content + threshold render beats GLM output — GLM's restyle passes drift (dropped strokes, noise chars, lost rows) and its reasoning burns thousands of tokens even when asked to disable thinking. Use GLM only as a stylistic suggestion, verify its art column-count and stroke continuity programmatically, and fall back to the deterministic render when a pass degrades.
- **App-embedded streaming (tutor, chat assistant): choose the model by measured time-to-first-token, not quality tier.** Probe the coding endpoint with the real key and a one-sentence prompt (parse the key in the script; print timings only). Observed on the dev key (n=1, directional — re-run before fixing a number): `glm-5.3` ≈ 17 s to first token (reasoning precedes any answer byte, even though its long-output throughput is higher); `glm-5.3-flash` ≈ 3 s by default and ≈ 2.3 s with `thinking: {"type":"disabled"}`. That ~2.3 s is a network+queue floor, so an app target like "first token < 2 s" is unreachable on this backend: state a GLM-specific target and keep the original for the production backend. `reasoning_effort` low/medium produced no reasoning on a trivial prompt, same as the explicit switch; prefer the explicit `thinking` field. z.ai's docs say 5.3-class models reject `disabled`, yet the coding endpoint accepted it on flash — if it starts erroring, delete the field rather than switching model. Request `stream_options: {"include_usage": true}` and meter from the final chunk's `usage` (prompt, completion, `completion_tokens_details.reasoning_tokens`) instead of estimating; the plan is prepaid, so token caps (not dollar caps) are what can trip.
- One retry after a transient failure, then switch engine or go direct — do not loop on a failing harness.
- **OpenCode + zai-coding-plan: use the dedicated `zai-coding-plan` provider entry (baseURL `https://api.z.ai/api/coding/paas/v4`), not a generic `zai-public` provider.** The coding-plan key is scoped to the coding endpoint; a public-endpoint provider with the same key fails confusingly. Smoke order when OpenCode run fails: (1) direct curl of the completions endpoint (200 = API fine), (2) trivial prompt `Reply OK` (works = prompt-triggered crash, not provider), (3) `opencode --print-logs --log-level DEBUG run` and grep the real error before blaming the model.
- Vision/image analysis via GLM-family or budget-limited vision APIs can hard-fail (HTTP 429 'insufficient balance') — before routing screenshot review through a vision model, try programmatic pixel analysis (PIL color sampling/bbox detection) for geometry questions like 'is this element aligned/rendered'; it answers layout questions deterministically and for free.

## Telegram quiet mode (added 2026-09-06)
- `display.tool_progress_overrides: {telegram: off}` — Telegram sees only final
  messages + approval prompts. Value must be exactly `off` (`none` silently does
  nothing — hermes-agent issue #50710).
- CLI keeps `display.tool_progress: all` (live feed untouched).
- Reasoning display already off (`display.show_reasoning: false`); streaming
  drafts for Telegram remain on (`display.platforms.telegram.streaming: true`)
  — that's the response itself, not tool noise.
- In-chat escape hatch: `/verbose` cycles display modes per platform.

## How it was configured
- Always `hermes config set KEY VAL` — never hand-edit config.yaml (hard invariant).
- List/dict values passed as quoted JSON flow style.
- Config backup before changes: `~/.hermes/config.yaml.bak-smartrouting-*`.
- Verified with `hermes chat --provider moa --model deep -q ...` and a plain
  `hermes chat -q ...` run before declaring done.
