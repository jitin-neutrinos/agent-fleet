# graphify-shared (agent-fleet)

ONE graphify MCP server on HTTP for all harnesses — replaces per-harness
stdio spawns (each ~780MB after loading the merged graph; 6 were running).

- Unit: ~/.config/systemd/user/graphify-shared.service
- Endpoint: http://127.0.0.1:8390/mcp (stateless, session reap 900s)
- Graph: ~/Work/graphify-out/merged-graph.json (refreshed nightly by
  graphify-refresh / discovered by graphify-discover — unchanged)
- Guards: MemoryMax=1500M, ManagedOOMMemoryPressure kill @60%

Wiring (all point at the HTTP endpoint, no local processes):
- hermes:   ~/.hermes/config.yaml  mcp.graphify.url
- opencode: ~/.config/opencode/opencode.json  mcp.graphify (type remote)
- claude:   ~/.claude.json  mcpServers.graphify (type http)
- gemini:   ~/.gemini/config/mcp_config.json  mcpServers.graphify (httpUrl)
- fleet lists: hermes.list / claude.list rows below

Migrated 2026-09-26. Backups: ~/.config-backups/20260926-graphify-shared/
