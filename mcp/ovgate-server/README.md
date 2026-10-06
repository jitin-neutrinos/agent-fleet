# ovgate — Laya memory-write gate for OpenViking

Filtering proxy 127.0.0.1:1934 -> OpenViking 1933. Deterministic delete-protection
(memories/decisions/preferences namespaces -> HITL confirm), near-dup write skip via
ov find similarity, Laya second opinion on fuzzy deletes. Fail-open; decisions logged
(~/.hermes/logs/ovgate.log) + hash-chained receipts.

Deploy: systemd user unit ovgate.service (ExecStart=...ovgate/server.py, EnvironmentFile
~/.hermes/.env for LAYA_MCP_TOKEN). Harnesses point at http://127.0.0.1:1934/mcp.
