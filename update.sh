#!/usr/bin/env bash
# update.sh — consumer-side agent-fleet refresh.
# For machines that CONSUME the store (the desktop is the source of truth and pushes
# instead). Pulls the repo, then mirrors skills into every local harness dir found.
# Idempotent; safe to run from a systemd timer. MCP/plugin changes are NOT applied
# here — re-run install.sh for those.
set -u
AF_DIR="${AF_DIR:-$HOME/agent-fleet}"
cd "$AF_DIR" || { echo "[af-update] no store at $AF_DIR"; exit 1; }

if [ -d .git ]; then
  if git pull --ff-only -q 2>/dev/null; then
    echo "[af-update] pulled $(git log -1 --format=%h)"
  else
    echo "[af-update] pull failed/skipped (offline or auth) — mirroring existing copy"
  fi
fi

mirror() {  # mirror <target-dir> — categorised tree, for any-depth readers (hermes, opencode)
  [ -n "$1" ] || return 0
  [ -d "$(dirname "$1")" ] || return 0
  rsync -a --delete --exclude=.git "$AF_DIR/skills/" "$1/" && echo "[af-update] skills -> $1"
}

mirror_flat() {  # mirror <target-dir> as depth-1 skills/<name>/SKILL.md (Claude Code, Antigravity)
  [ -n "$1" ] || return 0
  [ -d "$(dirname "$1")" ] || return 0
  stage="$(mktemp -d)"
  for d in "$AF_DIR"/skills/*/; do
    [ -f "$d/SKILL.md" ] || continue
    cp -a "$d" "$stage/$(basename "$d")"
  done
  for d in "$AF_DIR"/skills/*/*/; do
    [ -f "$d/SKILL.md" ] || continue
    n="$(basename "$d")"; [ -e "$stage/$n" ] && continue
    cp -a "$d" "$stage/$n"
  done
  rsync -a --delete "$stage/" "$1/" && echo "[af-update] flat skills -> $1"
  rm -rf "$stage"
}

[ -d "$HOME/.hermes" ] && mirror "$HOME/.hermes/skills"
for p in "$HOME"/.hermes/profiles/*/; do
  [ -d "${p}skills" ] && mirror "${p}skills"
done
[ -d "$HOME/.claude" ] && mirror_flat "$HOME/.claude/skills"
[ -d "$HOME/.config/opencode" ] && mirror "$HOME/.config/opencode/skills"
if [ -d "$HOME/.gemini" ]; then
  mirror_flat "$HOME/.gemini/config/skills"
  [ -d "$HOME/.gemini/antigravity" ] && mirror_flat "$HOME/.gemini/antigravity/global_skills"
fi

echo "[af-update] done — store has $(find "$AF_DIR/skills" -name SKILL.md 2>/dev/null | wc -l) skills"

# Rulebooks: refresh the tool-router mandate (marker-delimited, idempotent).
if [ -f "$AF_DIR/rules/install-rulebooks.sh" ]; then
  bash "$AF_DIR/rules/install-rulebooks.sh" || echo "[af-update] rulebook leg failed (continuing)"
fi

# Observability: push a health report to the master (best-effort; skipped silently
# when this node has no ~/.config/agent-fleet/health.env).
if [ -x "$AF_DIR/health/node-report.sh" ]; then
  bash "$AF_DIR/health/node-report.sh" || true
fi
