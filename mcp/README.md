# MCP portability notes

Formats:
- `hermes.list` / `claude.list`: `name|kind|spec|args|ENV_NAMES|notes` (pipe-separated).
  `kind` is `http` or `stdio`. A spec beginning `MACHINE_LOCAL:` carries a desktop
  absolute path — installers resolve or skip it per machine.
- `opencode.json`: `mcp` block merged into `~/.config/opencode/opencode.json`.
- `gemini.json`: `mcpServers` block merged into `~/.gemini/settings.json`.

MACHINE_LOCAL entries (desktop-only, skipped elsewhere):
- `computer-use-linux` — ~/.npm-global/bin/computer-use-linux (desktop binaries)
- `kwin` — ~/.local/bin/kwin-mcp (KDE desktop control)

Never synced (OAuth-bound, account-specific): claude.ai n8n, Miro, Figma, Lovable,
Microsoft 365. These authenticate via claude.ai OAuth and are excluded at sync time
(jq-stripped from `mcp/reference/claude.json`) and never appear in any *.list.

Env keys referenced (names only, values collected at install time):
- CONTEXT7_API_KEY (context7 auth header)
- HF_TOKEN (mcp-hfspace)
- AGENTMEMORY_URL / AGENTMEMORY_SECRET / AGENTMEMORY_TOOLS (agentmemory MCP;
  URL/TOOLS have safe defaults, SECRET usually empty on laptop)

- `laya-decisions` — http://127.0.0.1:8015/mcp — Laya decision-engine MCP (runs on kurama-core, systemd `laya-mcp.service`); agy added via `agy mcp add`.
- server source: mcp/laya-mcp-server/ (systemd unit + install steps in its README)
