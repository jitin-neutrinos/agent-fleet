#!/usr/bin/env bash
# harness/gemini.sh — install fleet into Gemini CLI.
set -u
AF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$AF_DIR/lib/common.sh"

af_have gemini || { af_skip "gemini: not installed"; exit 0; }
command -v jq >/dev/null || af_die "jq required"

G_CFG="$HOME/.gemini/settings.json"

if [ "$AF_DRY_RUN" != "1" ]; then
  mkdir -p "$HOME/.gemini"
  [ -f "$G_CFG" ] && [ ! -f "$G_CFG.pre-agent-fleet.bak" ] && cp "$G_CFG" "$G_CFG.pre-agent-fleet.bak"
  touch "$G_CFG"; [ -s "$G_CFG" ] || echo '{}' > "$G_CFG"
  tmp="$(mktemp)"
  jq --slurpfile fleet "$AF_DIR/mcp/gemini.json" \
    '.mcpServers = ((.mcpServers // {}) + $fleet[0].mcpServers)' "$G_CFG" > "$tmp" \
    && mv "$tmp" "$G_CFG"
  af_ok "gemini mcpServers merged"
else
  af_log "[dry-run] would merge mcp/gemini.json into $G_CFG"
fi

# gemini CLI has no native skills dir — skip skills (ponytail: don't invent one).
af_manifest gemini_mcp "$(jq -c '[.mcpServers | keys[]]' "$G_CFG" 2>/dev/null || echo '[]')"
af_manifest gemini_skills '"skipped (gemini has no native skills dir)"'
af_ok "gemini leg done"
