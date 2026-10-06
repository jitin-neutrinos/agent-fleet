# graphify-server (agent-fleet)

Local graphify knowledge-graph stack: maps every `~/Work` project into a
queryable knowledge graph and serves ONE merged master graph to all harnesses
via MCP (`graphify-mcp`). Semantic extraction runs on LOCAL ollama
(`qwen3.5:9b-128k`) — free, unlimited. Do NOT use the gemini backend for fleet
mapping: free tier allows only 20 requests/day and burns out mid-fleet.

## Components

- `graphify-refresh` — nightly freshness: AST-only incremental updates per
  project (free), semantic re-extract only when `check-update` flags drift,
  then merges all graphs into `~/Work/graphify-out/merged-graph.json`.
- `graphify-discover` — every 30 min: finds project-shaped dirs under `~/Work`
  (marker files: package.json, pyproject.toml, Cargo.toml, go.mod, ...) that
  have no graph, maps them, re-merges the master. Opt out per dir:
  `touch <project>/.graphify-skip`.
- `graphify-discover.timer` / `.service` — systemd user units.
- Locking: both scripts `flock` `~/.cache/graphify-discover.lock`; concurrent
  runs are skipped, never interleaved.

## Install (kurama-core shape)

1. `uv tool install "graphifyy[gemini]" --force --with mcp` (extras pull the
   openai pkg + the `mcp` pkg that graphify-mcp needs to serve stdio)
2. `install -m755 graphify-discover graphify-refresh ~/.local/bin/`
3. `cp graphify-discover.{timer,service} ~/.config/systemd/user/`
4. `systemctl --user daemon-reload && systemctl --user enable --now graphify-discover.timer`
5. Harness wiring (already in `mcp/*.list` / `opencode.json` / `gemini.json`):
   `graphify-mcp <master graph>` stdio server for hermes/claude/opencode/gemini.
6. Skill registration: `graphify install --platform claude` (and opencode /
   hermes / antigravity / gemini as needed) + always-on AGENTS.md blocks.
   OpenCode: `~/.config/opencode/AGENTS.md`; Hermes/agents: `~/AGENTS.md`.

## Operational notes

- Image-heavy repos: a `.graphifyignore` with `*.png *.jpg *.jpeg *.webp *.gif`
  keeps the local VLM out of screenshot dirs (minutes per image otherwise).
- Logs: `~/Work/graphify-fleet.log`, `~/Work/graphify-discover.log`,
  `~/Work/graphify-refresh.log`.
- One-shot fleet map of all standard projects: `~/Work/scratch/graphify-fleet.sh`.
- MCP server probe: `graphify-mcp <graph.json>` starts and speaks stdio MCP;
  registered in Hermes config as `graphify` (enabled).
