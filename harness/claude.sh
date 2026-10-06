#!/usr/bin/env bash
# harness/claude.sh — install fleet into Claude Code.
set -u
AF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$AF_DIR/lib/common.sh"

af_have claude || { af_skip "claude: not installed"; exit 0; }
command -v rsync >/dev/null || af_die "rsync required"

# ---- skills -----------------------------------------------------------------
# Claude Code discovers ONLY depth-1 skills: ~/.claude/skills/<name>/SKILL.md.
# The store keeps skills categorised (skills/<category>/<name>/SKILL.md), so
# stage a flat copy before installing — otherwise Claude never sees them.
stage="$(mktemp -d)"
for d in "$AF_DIR"/skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  cp -a "$d" "$stage/$(basename "$d")"
done
dupes=""
for d in "$AF_DIR"/skills/*/*/; do
  [ -f "$d/SKILL.md" ] || continue
  n="$(basename "$d")"
  if [ -e "$stage/$n" ]; then dupes="$dupes $n"; continue; fi
  cp -a "$d" "$stage/$n"
done
[ -n "$dupes" ] && af_warn "duplicate skill names, first copy kept:$dupes"
af_run "install flat skills -> ~/.claude/skills" rsync -a --delete "$stage/" "$HOME/.claude/skills/"
rm -rf "$stage"

# ---- plugins (marketplace route) --------------------------------------------
if [ "$AF_DRY_RUN" != "1" ]; then
  if claude plugin marketplace list 2>/dev/null | grep -q agent-fleet; then
    af_log "marketplace agent-fleet present; updating"
    claude plugin marketplace update >/dev/null 2>&1 || true
  else
    af_run "claude plugin marketplace add jitin-neutrinos/agent-fleet" \
      claude plugin marketplace add jitin-neutrinos/agent-fleet
  fi
  for p in ponytail caveman; do
    if claude plugin list 2>/dev/null | grep -q "$p"; then
      af_log "plugin $p already installed"
    else
      af_run "claude plugin install $p@agent-fleet" claude plugin install "$p@agent-fleet" --scope user
    fi
  done
else
  af_log "[dry-run] would add marketplace + install ponytail@caveman plugins"
fi

# ---- MCPs -------------------------------------------------------------------
claude_mcp_present() { claude mcp list 2>/dev/null | grep -qE "^$1:"; }

tmpi="$(mktemp)"; tmps="$(mktemp)"; echo "[]" > "$tmpi"; echo "[]" > "$tmps"
add_json() { python3 -c 'import json,sys; l=json.load(open(sys.argv[1])); l.append(sys.argv[2]); json.dump(l, open(sys.argv[1],"w"))' "$1" "$2"; }

while IFS='|' read -r name kind spec args envs notes; do
  [ -z "$name" ] && continue
  case "$name" in \#*) continue ;; esac

  skip=""
  if [ -n "$envs" ]; then
    IFS=',' read -ra KEYS <<< "$envs"
    for k in "${KEYS[@]}"; do
      [ -z "$k" ] && continue
      if [ -z "$(af_env_get "$k")" ]; then
        af_prompt_key "$k" "claude MCP $name"
        rc=$?
        if [ $rc -eq 2 ]; then
          af_skip "$name: env key $k not provided"
          add_json "$tmps" "$name (env key $k not provided)"
          skip=1; break
        fi
      fi
    done
  fi
  [ -n "$skip" ] && continue

  if claude_mcp_present "$name"; then af_log "$name already in claude (skip)"; add_json "$tmpi" "$name (already present)"; continue; fi

  if [ "$kind" = "http" ]; then
    af_run "claude mcp add $name (http)" \
      claude mcp add --scope user --transport http "$name" "$spec"
  else
    # shellcheck disable=SC2086
    af_run "claude mcp add $name (stdio)" \
      claude mcp add --scope user "$name" -- "$spec" $args
  fi
  add_json "$tmpi" "$name"
done < "$AF_DIR/mcp/claude.list"

af_manifest claude_installed "$(cat "$tmpi")"
af_manifest claude_skipped "$(cat "$tmps")"
rm -f "$tmpi" "$tmps"

skillcount="$(find "$HOME/.claude/skills" -name SKILL.md 2>/dev/null | wc -l)"
af_manifest claude_skills "$skillcount"
af_ok "claude leg done (skills: $skillcount)"
