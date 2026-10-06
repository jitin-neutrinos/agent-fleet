#!/usr/bin/env bash
# health/node-report.sh — node-side observability for the agent-fleet store.
# Runs at the end of update.sh (every 6h on pull-nodes) and standalone on demand.
# Collects this node's store state, appends to a local log (5-day retention), and
# pushes one JSON report to the master over the existing key-based SSH (no password,
# no token on the node). Read-only checks — safe from a timer.
set -u
AF_DIR="${AF_DIR:-$HOME/agent-fleet}"
CONF="${AF_CONF:-$HOME/.config/agent-fleet/health.env}"
# Report only from provisioned nodes. A health.env alone is not enough: the master's holds
# alert credentials but no node identity, so require NODE_NAME (set when a node is onboarded).
# Non-nodes (the master, or a machine sync runs update.sh on for consumer mirrors) skip cleanly.
if [ ! -f "$CONF" ]; then echo "[af-report] no health.env at $CONF — skipped"; exit 0; fi
# shellcheck disable=SC1090
. "$CONF"
if [ -z "${NODE_NAME:-}" ]; then echo "[af-report] $CONF names no node — skipped"; exit 0; fi
NODE_NAME="${NODE_NAME:-$(hostname | tr '[:upper:]' '[:lower:]')}"
# Default master = fleet-wide property (single-master design); a node can override
# via NODE_NAME/MASTER_SSH in ~/.config/agent-fleet/health.env (0600).
MASTER_SSH="${MASTER_SSH:-notjitin@100.97.142.40}"
LOG="${NODE_HEALTH_LOG:-$HOME/.agent-fleet-health.log}"
now_iso=$(date -Iseconds)
cd "$AF_DIR" 2>/dev/null || { echo "[af-report] no store at $AF_DIR"; exit 0; }

count() { find "$1" -name SKILL.md 2>/dev/null | wc -l; }
store=$(count skills); hermes=$(count "$HOME/.hermes/skills")
claude=$(count "$HOME/.claude/skills"); opencode=$(count "$HOME/.config/opencode/skills")
head=$(git rev-parse --short HEAD 2>/dev/null || echo none)
subject=$(git log -1 --format=%s 2>/dev/null | head -c 100)
remote_head=$(timeout 30 git ls-remote origin -h refs/heads/main 2>/dev/null | cut -c1-7)
behind=false; [ -n "$remote_head" ] && [ "$remote_head" != "$head" ] && behind=true
timer=$(systemctl is-active agent-fleet-update.timer 2>/dev/null || echo n/a)
last_status=$(systemctl show agent-fleet-update.service -p ExecMainStatus --value 2>/dev/null || echo n/a)
disk=$(df -h --output=avail "$HOME" 2>/dev/null | tail -1 | tr -d ' ')
# Flat (depth-1) consumers cannot hold duplicate skill names — staged-flat mirrors keep the
# first copy and drop later duplicates (xlsx), so their expected count is the number of
# DISTINCT skill-dir basenames, not the store's raw SKILL.md count.
flat_expected=$(find skills -name SKILL.md 2>/dev/null | awk -F/ '{print $(NF-1)}' | sort -u | wc -l)
conform=false
[ "$store" -gt 0 ] && [ "$store" = "$hermes" ] && [ "$store" = "$opencode" ] && [ "$claude" = "$flat_expected" ] && conform=true

json=$(jq -n --arg node "$NODE_NAME" --arg ts "$now_iso" --arg head "$head" --arg subject "$subject" \
  --argjson store "$store" --argjson hermes "$hermes" --argjson claude "$claude" --argjson opencode "$opencode" \
  --arg remote "$remote_head" --argjson behind "$behind" --argjson conform "$conform" \
  --arg timer "$timer" --arg last "$last_status" --arg disk "$disk" \
  '{node:$node, ts:$ts, store_head:$head, subject:$subject,
    skills:{store:$store, hermes:$hermes, claude:$claude, opencode:$opencode},
    remote_head:$remote, behind_origin:$behind, conformant:$conform,
    update_timer:$timer, last_update_status:$last, disk_avail:$disk}')

mkdir -p "$(dirname "$LOG")"
printf '%s %s\n' "$now_iso" "$(printf '%s' "$json" | tr -d '\n')" >> "$LOG"
cut=$(date -d '-5 days' +%Y-%m-%d)
awk -v c="$cut" '$1 >= c' "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

if [ -n "$MASTER_SSH" ] && timeout 8 ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$MASTER_SSH" true 2>/dev/null; then
  printf '%s\n' "$json" | timeout 20 ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$MASTER_SSH" \
    "mkdir -p agent-fleet-health && cat > agent-fleet-health/node-${NODE_NAME}.json.tmp && mv agent-fleet-health/node-${NODE_NAME}.json.tmp agent-fleet-health/node-${NODE_NAME}.json" \
    && echo "[af-report] $NODE_NAME pushed to $MASTER_SSH (head $head, store $store skills)" \
    || echo "[af-report] push to master failed — report kept locally"
else
  echo "[af-report] master unreachable — report kept locally ($LOG)"
fi
