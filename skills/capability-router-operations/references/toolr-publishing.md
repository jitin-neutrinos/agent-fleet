# ToolR publishing & product state

Working tree `~/Work/tool-router`; public as **ToolR** (github.com/jitin-neutrinos/ToolR,
master branch). The skill tree is symlinked (`~/toolr -> ~/Work/tool-router`), so the
installed entrypoint always runs the working code — never re-clone after edits.

## Publishing pipeline

```bash
cd ~/Work/tool-router
git -c user.name=hermes -c user.email=hermes@local commit -m "..." && git push
bash tools/deploy.sh            # tarball + install.sh + SHA256SUMS -> ~/Work/toolr-www
```

Served by `toolr-www.service` (user unit, `tools/serve-www.py`, 127.0.0.1:8030) behind
the `jitinnair-personal` cloudflared tunnel; hostname `toolr.jitinnair.com` (CNAME added).
One-liner: `curl -fsSL https://toolr.jitinnair.com/install.sh | bash`.
Cache policy: hash-named artifacts immutable forever; mutable entrypoints
(install.sh, SHA256SUMS) `no-store` — a naive static server let the edge cache a stale
 installer against a moved repo.

## Delivery wiring (verified live)

- **Claude Code**: UserPromptSubmit hook (`settings.json`) → `route.py --hook`.
  Enforcement (deny-once PreToolUse `gate.py --check` + PostToolUse `gate.py --loaded`)
  wired and backed up (`settings.json.bak-toolr-enforce`).
- **Hermes gateway (Astra/Android/Telegram/TUI)**: plugin enabled in config.yaml
  `plugins.enabled` — PRESENT-ON-DISK ≠ ENABLED; grep the gateway logs for the card
  marker to prove delivery. `pre_gateway_dispatch` stamps the session model as
  `HERMES_MODEL` for the resolver, and on webui/android surfaces appends an
  astra-canvas block (picks table + decision context) parsed FROM the emitted card —
  display-only, the model still gets the markdown card.
- **Adoption harvest**: `toolr-adopt.timer` daily 10:45 IST → `scripts/adoptcollect.py`
  → `eval/adoption.jsonl`; layer-3 depth adjustment consumes it once a 24h span exists.
- State dir `~/.tool-router/`: index.json (tokens stripped on save, re-derived on load
  WITH aliases+bodies), `index.dense.npz` (Ollama nomic-embed-text; full rebuild = move
  `.npz` AND `.meta.json` aside), `learned.json` (Skill-load prior, +0.25 clamp 2.0),
  `breaker-*.json` (delete to reset), `last_route.json` (gate's suggestion state),
  `config.json` (`fusion_alpha`, `kind_quota`, `mcp_hints`, `decision`).
