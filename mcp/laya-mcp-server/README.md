# laya-mcp server (Laya decision engine)

Runs on a machine with the `laya` Python package (CPU is fine, ~140ms/call).
Unit: `~/.config/systemd/user/laya-mcp.service` (Env LAYA_DEVICE=cpu, LAYA_PRELOAD=1).

Install:
    uv venv .venv --python 3.12
    VIRTUAL_ENV=$PWD/.venv uv pip install "laya" "fastapi" "uvicorn" "httpx" "mcp<2"
    LAYA_DEVICE=cpu LAYA_PRELOAD=1 .venv/bin/python server.py   # port 8015

Machines without a local server: point the harness MCP entry at
https://laya-decision-mcp.jitinnair.com/mcp (Cloudflare tunnel -> kurama-core:8015).
