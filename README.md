# agent-fleet

Global personal harness store: one private repo holding skills, plugins, and MCP
definitions for Hermes, Claude Code, OpenCode, and Gemini CLI. Any machine runs:

```
curl -fsSL https://harness.jitinnair.com/install.sh | bash
```

Install: clones this repo to `~/agent-fleet`, detects harnesses, mirrors skills,
installs plugins/MCPs, prompts for missing env keys (never stored in the repo),
writes a per-machine manifest to `state/`.

Layout: `install.sh` (orchestrator) · `harness/*.sh` (per-harness legs) ·
`lib/common.sh` (detection, keys, manifest) · `sync-from-desktop.sh` (desktop push,
runs every 6h via systemd user timer) · `skills/` (superset, from Hermes) ·
`plugins/` (hermes plugins + claude marketplace with ponytail/caveman) ·
`mcp/` (declarative defs per harness; MACHINE_LOCAL markers; see mcp/README.md).

Secrets never live here — installer collects keys via `read -s` at install time.
Claude.ai OAuth MCPs (n8n/Miro/Figma/Lovable/MS365) are deliberately excluded.
