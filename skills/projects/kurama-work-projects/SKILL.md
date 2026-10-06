---
name: kurama-work-projects
description: "Use for any work in the Work-folder projects on kurama-core."
---

# ~/Work projects on kurama-core (reviewed 2026-09-05)

Scope: all five projects under host path `/home/notjitin/Work` — coding-harness,
streamer, local-av-gen, Hermes, Neutrinos.

In Hermes docker sessions the folder appears only when bind-mounted (found at
`/home/notjitin/Work` via findmnt; sandbox `/workspace` is
`.hermes/sandboxes/docker/default/workspace`, a different dir).

## coding-harness — local agentic coding rig (git)
Docker compose stack: OpenCode 1.18.25 (pinned, digest-pinned ubuntu:24.04 base) +
Ollama + SearXNG on `harness_net`, server on 127.0.0.1:4096 with basic auth.
Model: Qwen3.8-27B `IQ3_XXS` (10.9 GB, 66/66 layers on the 4070 Ti SUPER).
Journey: enhancement_plan.md (43 KB, 5 fatal defects found live 2026-09-02, all fixed)
then bench/RESULTS.md — Q4_K_M to IQ3_XXS plus reasoning_effort fix took the agentic
suite from 104.9s to 42.7s avg (2.5x), 39.7 tok/s, 4/4 PASS exact-assert checkers.
Serena MCP removed (cost 5,233 tok/turn). 2026-09-05 — ported ponytail (real OpenCode
plugin @dietrichgebert/ponytail@4.9.0), caveman core skill, context7 hosted MCP.
Old Q4_K_M model tags (~17 GB each, two) on disk pending reclaim decision.

## streamer — Nobara to Windows game/desktop streaming (git)
Sunshine (GloriousEggroll fc44 build) over Tailscale SSH; Moonlight client.
STATUS.md (2026-09-04) is the source of truth; plan.md v3 superseded in 4 places;
enhancement-plan.md is the current design. Working and verified: KWin ScreenCast
capture (`capture = kwin`), krfb-virtualmonitor at client resolution, office panel
blank via 3s watchdog, 3-layer restore, NVENC h264/hevc/av1, mDNS silenced,
tailnet-zone firewalld, autologin via plasma-login-manager (no sddm). Test suites:
19/19 and 22/22. Call of Duty = RICOCHET kernel anti-cheat, never runnable on Linux
(vendor decision). Untested: real home-internet path, bitrate/codec choice (start
HEVC 20 Mbps), kwin freeze reports (#5241). Next steps listed at STATUS.md bottom.

## local-av-gen — local image/video generation
ComfyUI container (mmartial/comfyui-nvidia-docker, tag+digest pinned, gpus all,
127.0.0.1:8188) on external `workspaces` network. TORCH_LOCK pins a matched
torch 2.13.0+cu129 trio (blocks ComfyUI unpinned reqs). Models live on NTFS at
/run/media/notjitin/405AE5E75AE5D9A4/AI_Models/comfyui_models (bind; never write
NTFS). Custom nodes: ComfyUI-GGUF, TTS-Audio-Suite, kjnodes. Workflows/scripts:
z-image-turbo, Wan2.2 i2v, chatterbox TTS, InfiniteTalk, TRELLIS2, wav2vec. Real
outputs in data/output/ (ShiftAndShadow sets, flac, mp4). docs/implementation-plan.md
34 KB. scripts/check.sh + localgen.sh.

## Hermes — the assistant itself (docs only; code deleted Phase 9)
Hermes runs host-native at ~/.hermes (systemd --user gateway + dashboard :9119,
linger on). Profiles: default (orchestrator, kanban/memory only), coder (claude -p),
reviewer (agy -p), researcher, desktop (kwin HITL), ops (host shell). Agent shell =
docker (nikolaik/python-nodejs digest-pinned). enhancement-plan.md — 9 phases; the
containerized rewrite was dropped (3.34 GB dead weight, open VNC) for host-native.
docs/memory-enrichment-plan.md (2026-09-05, PROPOSAL, unapplied) — MEMORY.md at 395
percent of limit (8,689/2,200), every memory add fails; phases 0-3 cover store
reload, unbounded tier, provider chain, cron hygiene.

## Neutrinos — work (day-job) material, not code
Call Data/AI Hub Adoption Strategy Meeting — transcript, summary, checklist. Suresh
(CTO) rejected Jitin's champion-selection strategy (academy scores gamed, telemetry
shallow); verdict — redo after completing his own 82 percent certification, aligning
with pre-sales (DJ), interviewing customer teams, then a playback session.
AI Hub/docs/ is empty.

## Cross-project facts
- GPU budget is shared: harness IQ3_XXS inference vs ComfyUI generation vs Sunshine
  NVENC — check VRAM before running heavy jobs concurrently.
- Two compose networks: `workspaces` (local-av-gen) and `harness_net`
  (coding-harness); Hermes documented as allowed to join harness_net externally.
- All images tag+digest pinned per house rules; secrets via .env (never committed).
- Per-project doc pattern: large audited plan files, STATUS/RESULTS newest-wins.

## astra — auto-port pitfall (learned 2026-09-15)
GitHub compare API (auto_port.py `--check`) truncates `files[]` at 300; a
large upstream jump (396 commits / 904 changed files) surfaced as only 2 files
and a wrong PORT-NEEDED. When commits_behind is large or the watched list
looks suspiciously tiny, re-diff locally (`git -C ~/.hermes/hermes-agent diff
--name-status <baseline>..origin/main`) and run auto_port.classify() on the
full list — routers-modified and removed modules are ESCALATE class, owner
decides. Astra page plugins consume the web-UI slot/SDK surface only, not
web_routers directly.
