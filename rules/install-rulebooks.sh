#!/usr/bin/env bash
# rules/install-rulebooks.sh — write the tool-router mandate into every
# detected harness's rulebook (idempotent, marker-delimited).
# Requirement: every machine installed from the agent-fleet store carries the
# canonical tool-router contract (route-before-work + sourcing policy).
set -u
AF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES_SRC="$AF_DIR/rules/tool-router-mandate.md"

af_have() {
  command -v "$1" >/dev/null 2>&1
}

# local logging fallbacks (lib/common.sh may not be sourced in this context)
af_log() { printf '[af] %s\n' "$*"; }
af_ok()  { printf '[af:ok] %s\n' "$*"; }

write_block() {  # write_block <rulebook> — marker-delimited replace/append
  local f="$1"
  [ -f "$f" ] || mkdir -p "$(dirname "$f")"
  touch "$f"
  if grep -q '<!-- tool-router:begin -->' "$f"; then
    # replace between markers
    local tmp; tmp="$(mktemp)"
    awk -v repl_file="$RULES_SRC" '
      BEGIN { inblock=0; done=0 }
      /<!-- tool-router:begin -->/ {
        inblock=1
        while ((getline line < repl_file) > 0) print line
        done=1
        next
      }
      /<!-- tool-router:end -->/ { inblock=0; next }
      inblock { next }
      { print }
    ' "$f" > "$tmp" && mv "$tmp" "$f"
  else
    printf '\n' >> "$f"
    cat "$RULES_SRC" >> "$f"
    printf '\n' >> "$f"
  fi
}

count=0
declare -a RULEBOOKS=(
  "$HOME/AGENTS.md"
  "$HOME/.claude/CLAUDE.md"
  "$HOME/.config/opencode/AGENTS.md"
  "$HOME/.gemini/config/GEMINI.md"
  "$HOME/.codex/AGENTS.md"
  "$HOME/.gemini/GEMINI.md"
)
for f in "${RULEBOOKS[@]}"; do
  [ -d "$(dirname "$f")" ] || continue
  write_block "$f"
  count=$((count + 1))
  af_log "rulebook updated: $f"
done

if [ -f "$RULES_SRC" ] && [ "$count" -gt 0 ]; then
  af_ok "tool-router rulebooks installed on $count rulebook(s)"
else
  af_log "tool-router rulebooks: nothing done (source missing or no rulebook dirs)"
fi
