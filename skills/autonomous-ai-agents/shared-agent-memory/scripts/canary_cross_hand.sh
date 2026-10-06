#!/usr/bin/env bash
# Cross-hand canary: proves two different agents share ONE memory store.
# Usage: bash canary_cross_hand.sh
# Pass = both cross-reads return the other agent's exact token AND ground truth shows both.
set -u
TS=$(date +%s | tail -c 6)
A="KU-RAMA-A-$TS"
B="KU-RAMA-B-$TS"
REST=http://localhost:3111

curl -sf "$REST/agentmemory/health" >/dev/null || { echo "FAIL: server not healthy"; exit 1; }

echo "== agent A (hermes) writes $A"
hermes chat -q "Use the agentmemory MCP tools to save exactly: 'Canary $A'. Reply one line." >/dev/null 2>&1

echo "== agent B (claude) writes $B"
claude -p "Use the agentmemory MCP tools to save exactly: 'Canary $B'. Reply one line." \
  --allowedTools "mcp__agentmemory" --max-turns 8 >/dev/null 2>&1

echo "== A retrieves B (expect $B)"
hermes chat -q "Search agentmemory for canary $B. Reply the exact token only." 2>&1 | grep -oE "KU-RAMA-B-[0-9]+" | head -1

echo "== B retrieves A (expect $A)"
claude -p "Search agentmemory for canary $A. Reply the exact token only." \
  --allowedTools "mcp__agentmemory" --max-turns 8 2>&1 | grep -oE "KU-RAMA-A-[0-9]+" | head -1

echo "== ground truth (both must appear)"
curl -s -X POST "$REST/agentmemory/smart-search" -H 'Content-Type: application/json' \
  -d '{"query":"canary KU-RAMA","limit":10}' \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);[print("  -",(x.get("content") or x.get("title",""))[:60]) for x in d.get("results",[])]'
