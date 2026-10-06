#!/usr/bin/env bash
# harness/opencode.sh — install fleet into OpenCode.
set -u
AF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$AF_DIR/lib/common.sh"

af_have opencode || { af_skip "opencode: not installed"; exit 0; }
command -v rsync >/dev/null || af_die "rsync required"
command -v jq >/dev/null || af_die "jq required"

OC_CFG="$HOME/.config/opencode/opencode.json"
OC_SKILLS="$HOME/.config/opencode/skills"

# ---- skills -----------------------------------------------------------------
# Desktop migration: ~/Work/coding-harness/config/skills was the old location.
OLD_SKILLS="$HOME/Work/coding-harness/config/skills"
if [ -d "$OLD_SKILLS" ] && [ ! -d "$OC_SKILLS" ]; then
  af_run "migrate old opencode skills dir -> $OC_SKILLS" mkdir -p "$(dirname "$OC_SKILLS")"
  af_run "move old skills" mv "$OLD_SKILLS" "$OC_SKILLS"
fi

af_run "rsync skills -> $OC_SKILLS" \
  bash -c "mkdir -p '$OC_SKILLS' && rsync -a --delete '$AF_DIR/skills/' '$OC_SKILLS/'"

# ---- config: merge mcp block ------------------------------------------------
if [ "$AF_DRY_RUN" != "1" ]; then
  mkdir -p "$(dirname "$OC_CFG")"
  [ -f "$OC_CFG" ] && [ ! -f "$OC_CFG.pre-agent-fleet.bak" ] && cp "$OC_CFG" "$OC_CFG.pre-agent-fleet.bak"
  touch "$OC_CFG"; echo '{}' > "$OC_CFG" 2>/dev/null || true
  [ -s "$OC_CFG" ] || echo '{}' > "$OC_CFG"
  # drop entries whose required env is missing? keep simple: merge whole block.
  tmp="$(mktemp)"
  jq --slurpfile fleet "$AF_DIR/mcp/opencode.json" '.mcp = ((.mcp // {}) + $fleet[0])' "$OC_CFG" > "$tmp" \
    && mv "$tmp" "$OC_CFG"
  af_ok "opencode mcp block merged"
else
  af_log "[dry-run] would merge mcp/opencode.json into $OC_CFG"
fi

# ---- env exports for profile ------------------------------------------------
# Keys are written by the orchestrator via af_env_set_profile (bashrc block).

# ---- manifest ---------------------------------------------------------------
tmpi='[]'
if [ -f "$OC_CFG" ]; then
  tmpi="$(jq -c '[.mcp | keys[]]' "$OC_CFG" 2>/dev/null || echo '[]')"
fi
af_manifest opencode_mcp "$tmpi"
skillcount="$(find "$OC_SKILLS" -name SKILL.md 2>/dev/null | wc -l)"
af_manifest opencode_skills "$skillcount"
af_ok "opencode leg done (skills: $skillcount)"
