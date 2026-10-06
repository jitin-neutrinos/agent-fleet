#!/usr/bin/env bash
# install-mcp-everywhere.sh — detect all AI harnesses on this system and install
# (or remove) a remote MCP server into each one. Idempotent; safe to re-run.
#
# Usage:
#   install-mcp-everywhere.sh [URL]          # install (default URL below)
#   install-mcp-everywhere.sh --remove [name]
# Env: MCP_NAME overrides the registration name (default neutrinos-docs).
#
# Tested live against: Claude Code, agy/Antigravity, opencode, Hermes Agent,
# Gemini CLI. Codex/Cursor/VS Code/generic ~/.mcp.json handlers included but
# only fire when those harnesses exist on the host.

set -u

MCP_NAME="${MCP_NAME:-neutrinos-docs}"
MCP_URL="${1:-https://mcp.glitchzerolabs.com/mcp}"
MODE="install"

if [ "${1:-}" = "--remove" ]; then
  MODE="remove"
  MCP_NAME="${2:-neutrinos-docs}"
  MCP_URL=""
fi

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
skip() { printf '  \033[90m–\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; }
hdr()  { printf '\n\033[1m[%s]\033[0m\n' "$1"; }

have() { command -v "$1" >/dev/null 2>&1; }

do_claude() {
  hdr "Claude Code"
  if ! have claude; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    claude mcp remove "$MCP_NAME" >/dev/null 2>&1 && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  claude mcp add --transport http "$MCP_NAME" "$MCP_URL" >/dev/null 2>&1 \
    && ok "added $MCP_NAME -> $MCP_URL" || fail "add failed"
}

do_agy() {
  hdr "agy (Antigravity CLI)"
  if ! have agy; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    agy mcp remove "$MCP_NAME" >/dev/null 2>&1 && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  agy mcp add "$MCP_NAME" "$MCP_URL" >/dev/null 2>&1 \
    && ok "added $MCP_NAME -> $MCP_URL" || fail "add failed"
}

do_opencode() {
  hdr "opencode"
  if ! have opencode; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    opencode mcp remove "$MCP_NAME" >/dev/null 2>&1 && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  opencode mcp add "$MCP_NAME" --url "$MCP_URL" >/dev/null 2>&1 \
    && ok "added $MCP_NAME -> $MCP_URL" || fail "add failed"
}

do_hermes() {
  hdr "Hermes Agent"
  if ! have hermes; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    hermes mcp remove "$MCP_NAME" >/dev/null 2>&1 </dev/null && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  # hermes mcp add prompts via /dev/tty (piped stdin won't reach it) — write config.yaml
  # directly. hermes reads the 'mcp_servers' key; http entries are {'url': ...}.
  python3 - "$MCP_NAME" "$MCP_URL" <<'PYEOF'
import sys, yaml
name, url = sys.argv[1], sys.argv[2]
p = '/home/notjitin/.hermes/config.yaml'
cfg = yaml.safe_load(open(p)) or {}
key = next((k for k in cfg if 'mcp' in k.lower() and isinstance(cfg[k], dict) and cfg[k]), 'mcp_servers')
servers = cfg.setdefault(key, {})
servers[name] = {'url': url}
cfg[key] = servers
empty = cfg.get('mcpServers')
if key != 'mcpServers' and isinstance(empty, dict) and not empty:
    cfg.pop('mcpServers')
yaml.safe_dump(cfg, open(p, 'w'), sort_keys=False)
print(f'  \033[32m✓\033[0m added {name} -> {url} (config.yaml [{key}])')
PYEOF
}

do_codex() {
  hdr "Codex CLI"
  if ! have codex; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    codex mcp remove "$MCP_NAME" >/dev/null 2>&1 && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  codex mcp add "$MCP_NAME" --url "$MCP_URL" >/dev/null 2>&1 \
    && ok "added $MCP_NAME -> $MCP_URL" || fail "add failed (check codex mcp --help for URL support)"
}

do_gemini() {
  hdr "Gemini CLI"
  if ! have gemini; then skip "not installed"; return; fi
  if [ "$MODE" = "remove" ]; then
    gemini mcp remove "$MCP_NAME" >/dev/null 2>&1 && ok "removed $MCP_NAME" || skip "was not registered"
    return
  fi
  gemini mcp add "$MCP_NAME" --transport http "$MCP_URL" >/dev/null 2>&1 \
    && ok "added $MCP_NAME -> $MCP_URL" || fail "add failed"
}

do_cursor() {
  hdr "Cursor"
  local cfg="$HOME/.cursor/mcp.json"
  if [ ! -f "$cfg" ] && ! have cursor; then skip "not installed"; return; fi
  python3 - "$cfg" "$MCP_NAME" "$MCP_URL" "$MODE" <<'PYEOF'
import json, sys
path, name, url, mode = sys.argv[1:5]
try:
    cfg = json.load(open(path))
except Exception:
    print('  \033[90m–\033[0m no mcp.json yet')
    sys.exit(0)
cfg.setdefault('mcpServers', {})
if mode == 'remove':
    cfg['mcpServers'].pop(name, None)
else:
    cfg['mcpServers'][name] = {'url': url}
json.dump(cfg, open(path, 'w'), indent=2)
print(f'  \033[32m✓\033[0m {"removed" if mode=="remove" else "added"} {name}')
PYEOF
}

do_vscode() {
  hdr "VS Code / VS Code forks"
  local found=0
  for d in "$HOME/.vscode" "$HOME/.vscode-oss" "$HOME/.vscode-server"; do
    [ -d "$d" ] || continue
    found=1
    local cfg="$HOME/.config/Code/User/mcp.json"
    [ -f "$cfg" ] || { skip "no mcp.json found"; continue; }
    python3 - "$cfg" "$MCP_NAME" "$MCP_URL" "$MODE" <<'PYEOF'
import json, sys
path, name, url, mode = sys.argv[1:5]
cfg = json.load(open(path))
servers = cfg.setdefault('servers', cfg.setdefault('mcpServers', {}))
if mode == 'remove':
    servers.pop(name, None)
else:
    servers[name] = {'type': 'http', 'url': url}
json.dump(cfg, open(path, 'w'), indent=2)
print(f'  \033[32m✓\033[0m {"removed" if mode=="remove" else "added"} {name} in {path}')
PYEOF
  done
  [ "$found" = "0" ] && skip "not installed"
}

do_generic_mcp_json() {
  hdr "Generic ~/.mcp.json (Cline/Windsurf/etc.)"
  local cfg="$HOME/.mcp.json"
  [ -f "$cfg" ] || { skip "no ~/.mcp.json present"; return; }
  python3 - "$cfg" "$MCP_NAME" "$MCP_URL" "$MODE" <<'PYEOF'
import json, sys
path, name, url, mode = sys.argv[1:5]
cfg = json.load(open(path))
servers = cfg.setdefault('mcpServers', {})
if mode == 'remove':
    servers.pop(name, None)
else:
    servers[name] = {'url': url}
json.dump(cfg, open(path, 'w'), indent=2)
print(f'  \033[32m✓\033[0m {"removed" if mode=="remove" else "added"} {name}')
PYEOF
}

echo "Neutrinos Docs MCP $MODE"
echo "  name: $MCP_NAME"
[ "$MODE" = "install" ] && echo "  url:  $MCP_URL"

do_claude
do_agy
do_opencode
do_hermes
do_codex
do_gemini
do_cursor
do_vscode
do_generic_mcp_json

echo
echo "Done. Restart any running harness sessions to pick up the change."