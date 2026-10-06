# neutrinos-mcp — service map + enhancement roadmap

Numbers below were live-measured once; re-probe before quoting them.

## Topology
- Code: `~/Work/Neutrinos/neutrinos-mcp` (git). Server core:
  `mcp-server/server.py` (~490 lines, FastMCP, 6 tools), venv at
  `mcp-server/.venv` (~5.9 GB; torch alone ~1.2 GB).
- Data: `~/.neutrinos-mcp/` (~532 MB): SQLite FTS5 chunks (~9.5K) +
  `embeddings.npz` (768-d float32, normalized).
- Retrieval: EmbeddingGemma-300M dense (sentence-transformers/torch, CPU,
  query-time prompt prefix Q_PROMPT) + bm25 → RRF fuse → results. No rerank
  stage. Evals: 88.8% recall@10 baseline, harness in repo.
- Public: `https://neutrinos-mcp.jitinnair.com/mcp` via the `neutrinos-client`
  cloudflared tunnel. Old domain `mcp.glitchzerolabs.com` is dead (530; CNAME
  points at a deleted tunnel) — never reuse in docs or DEFAULT_URLs.
- Units (systemd --user): `neutrinos-mcp.service` (server),
  `neutrinos-bridge.service` (nightly CSV→DB rebuild), `mcp-install-www.service`
  (static installer host).
- Installer: source of truth `~/scratch/install-neutrinos-docs-mcp.py`, public
  copies `~/scratch/mcp-install-www/{install.sh,install-neutrinos-docs-mcp.py}`.
  Adds the MCP to every detected harness (claude, agy, opencode, codex, gemini,
  hermes, generic ~/.mcp.json), per-harness pass/skip/fail reporting, flags
  --remove and positional URL override. Wrapper install.sh is 3 lines and must
  track the live domain in BOTH its comment and its curl line.

## Probes
- MCP alive: POST JSON-RPC initialize to /mcp (Accept: application/json,
  text/event-stream) → expect serverInfo `{name: neutrinos-docs, version: 4.x}`.
- Installer alive: GET /install.sh and /install-neutrinos-docs-mcp.py, check
  sizes AND that install.sh fetches the live domain.
- Service local: `systemctl --user is-active neutrinos-mcp.service`.

## Enhancement roadmap (evaluated, in order)
1. **Embedder runtime swap: torch → ONNX (fastembed-class).** Same model/vectors,
   ~2–4x CPU embed speed, 50–70% less RAM, deps ~2.8 GB → ~100 MB. Verify
   EmbeddingGemma-300M exists in the target runtime's model list or convert once;
   carry the Q_PROMPT query prefix across. Validate with the recall eval.
2. **Laya rerank after RRF.** Top ~15 fused → laya-mcp `rank`
   (127.0.0.1:8015/mcp, 77–150 ms/decision, $0, already running), margin-gated,
   fail-open to fused order. Pattern proven in tool-router. Validate vs 88.8%
   baseline; drop if no gain.
3. **Rejected: tiny-LLM query rewriting.** +1–5 s/query on CPU Ollama for
   marginal gain.
4. **Rejected: Rust rewrite of the HTTP daemon.** Persistent daemon — nobody
   pays the 0.57 s cold start; per-query time is SQLite/numpy (C); user latency
   is the LLM. The Rust-shaped product is a LOCAL stdio single-binary companion
   (official rmcp SDK, cross-compiled mac/win, offline docs) shipped through the
   installer. Route any 'rebuild in Rust' ask there.
