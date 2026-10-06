#!/usr/bin/env bash
# health/fleet-health.sh — desktop-side observability for the agent-fleet store.
# Runs on the master (kurama-core) from agent-fleet-health.timer (hourly) and at the
# end of every sync. Evaluates the store + the public installer site, ingests node
# reports, writes status.json + health.log (5-day retention), and posts to Telegram:
#   - a notice whenever the store head changes (regular "updates" feed)
#   - an alert whenever the overall colour changes (green/yellow/red)
#   - a daily green heartbeat when nothing else was sent
# Config: ~/.config/agent-fleet/health.env (0600). Never committed anywhere.
set -u
AF_DIR="${AF_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CONF="${AF_CONF:-$HOME/.config/agent-fleet/health.env}"
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

HD="${HEALTH_DIR:-$HOME/agent-fleet-health}"
STATE="$HD/state"; LOG="$HD/health.log"; STATUS="$HD/status.json"
mkdir -p "$HD" "$STATE"
now=$(date +%s)
color=green; issues=""
# canvas surface sync: every rulebook/skill must match the live parser schema (37 types / 12 kinds)
if [ -x "$AF_DIR/rules/canvas-surface-sync.mjs" ] || [ -f "$AF_DIR/rules/canvas-surface-sync.mjs" ]; then
  if ! node "$AF_DIR/rules/canvas-surface-sync.mjs" --check >/dev/null 2>"$HD/canvas-sync-drift.txt"; then
    note "canvas surfaces drift ($(wc -l <"$HD/canvas-sync-drift.txt" | tr -d ' ') targets)"; [ "$color" = green ] && escalate yellow
  fi
fi

escalate() { case "$1" in red) color=red ;; yellow) [ "$color" = green ] && color=yellow ;; esac; }
note() { issues="${issues}$1; "; }
log() { printf '%s %s\n' "$(date -Iseconds)" "$*" >> "$LOG"; }
jget() { jq -r "$1" "$2" 2>/dev/null; }
age_h() { [ -f "$1" ] && echo $(( (now - $(stat -c %Y "$1")) / 3600 )) || echo ""; }

tg_send_to() { # tg_send_to <chat_id> <text> — prints the error json on failure
  out=$(curl -s --max-time 20 -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        --data-urlencode chat_id="$1" --data-urlencode text="$2" 2>/dev/null)
  case "$out" in *'"ok":true'*) return 0 ;; esac
  printf '%s' "$out"; return 1
}
tg_discover_chat() { # a chat the bot has seen in pending updates (owner pressed START / added the bot)
  curl -s --max-time 15 "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates?limit=30" 2>/dev/null |
    jq -r '[.result[]? | (.message?.chat.id // .channel_post?.chat.id // .my_chat_member?.chat.id)] | map(select(. != null)) | last // empty' 2>/dev/null
}
tg() { # tg <text> — send to configured / remembered / discovered chat; 0 = delivered
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || return 2
  local c err=""
  for c in ${TELEGRAM_CHAT_ID:-} $(cat "$STATE/telegram-chat-id" 2>/dev/null); do
    [ -n "$c" ] || continue
    if err=$(tg_send_to "$c" "$1"); then echo "$c" > "$STATE/telegram-chat-id"; return 0; fi
  done
  # nothing worked — look for a newly started chat and wire it up automatically
  c=$(tg_discover_chat)
  if [ -n "$c" ]; then
    if err=$(tg_send_to "$c" "$1"); then
      echo "$c" > "$STATE/telegram-chat-id"
      tg_send_to "$c" "✅ agent-fleet alerts wired to this chat — store updates, health colours and downtime alerts will arrive here." >/dev/null
      log "telegram wired to chat $c"
      return 0
    fi
  fi
  log "telegram send failed: $(printf '%s' "$err" | head -c 200)"
  return 1
}

if [ "${1:-}" = "--selftest" ]; then
  if tg "🧪 agent-fleet telegram self-test — delivery works ($(date '+%F %T'))."; then
    echo "SENT — chat $(cat "$STATE/telegram-chat-id" 2>/dev/null | tail -1)"
  else
    echo "FAILED — press START in @Astral_Hermes_Alerts_bot, then retry. Details: $LOG"
  fi
  exit 0
fi

cd "$AF_DIR" || { log "no store at $AF_DIR"; exit 1; }

# ---- 1. sync freshness ------------------------------------------------------
sync_age=$(age_h "$STATE/last-sync-success")
if [ -z "$sync_age" ]; then escalate yellow; note "no successful sync recorded yet"
elif [ "$sync_age" -gt 14 ]; then escalate red; note "sync stale ${sync_age}h"
elif [ "$sync_age" -gt 7 ]; then escalate yellow; note "sync late ${sync_age}h"; fi

# ---- 2. repo vs origin ------------------------------------------------------
if timeout 40 git fetch -q origin 2>/dev/null; then
  head=$(git rev-parse --short HEAD 2>/dev/null)
  origin_head=$(git rev-parse --short origin/main 2>/dev/null)
  [ "$head" = "$origin_head" ] || { escalate red; note "repo $head != origin $origin_head"; }
else
  head=$(git rev-parse --short HEAD 2>/dev/null); origin_head="?"
  escalate red; note "git fetch failed (github unreachable / keyring)"
fi

# ---- 3. installer site ------------------------------------------------------
reposha=$(sha256sum install.sh | cut -d' ' -f1)
served=$(curl -fsS --max-time 15 http://127.0.0.1:8003/install.sh 2>/dev/null | sha256sum | cut -d' ' -f1)
pub=$(curl -fsS --max-time 25 https://harness.jitinnair.com/install.sh 2>/dev/null | sha256sum | cut -d' ' -f1)
if [ -z "$served" ]; then escalate red; note "local www server not serving install.sh"
elif [ "$served" != "$reposha" ] && [ "$served" = "$pub" ]; then
  escalate yellow; note "installer site one revision behind repo (sync pending)"
elif [ "$served" != "$reposha" ]; then escalate red; note "local www install.sh mismatch"; fiif [ -f "$REPO/install.ps1" ] 2>/dev/null || [ -f install.ps1 ]; then
  psha=$(sha256sum install.ps1 | cut -d' ' -f1)
  pserved=$(curl -fsS --max-time 15 http://127.0.0.1:8003/install.ps1 2>/dev/null | sha256sum | cut -d' ' -f1)
  ppub=$(curl -fsS --max-time 25 https://harness.jitinnair.com/install.ps1 2>/dev/null | sha256sum | cut -d' ' -f1)
  if [ -z "$pserved" ] || [ "$pserved" != "$psha" ]; then escalate red; note "install.ps1 served/psha mismatch ($psha vs $pserved)"; fi
  if [ -z "$ppub" ]; then escalate red; note "public harness.jitinnair.com install.ps1 unreachable"; fi
fi
if [ -z "$pub" ]; then escalate red; note "public harness.jitinnair.com install.sh unreachable"
elif [ "$pub" != "$served" ]; then escalate red; note "public site differs from local (tunnel/cache)"; fi

# ---- 3b. store UI + data ----------------------------------------------------
store_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8003/ 2>/dev/null)
[ "$store_code" = "200" ] || { escalate red; note "store UI not serving ($store_code)"; }
inv_skills=$(curl -fsS --max-time 15 http://127.0.0.1:8003/api/inventory.json 2>/dev/null | jq -r '.counts.skills' 2>/dev/null)
if [ -z "$inv_skills" ] || [ "$inv_skills" = "null" ]; then
  escalate red; note "store inventory.json unreadable"
elif [ "$inv_skills" -lt 400 ]; then escalate yellow; note "store inventory low ($inv_skills skills)"; fi

# ---- 4. units ---------------------------------------------------------------
systemctl --user is-active -q agent-fleet-sync.timer   || { escalate red; note "sync timer inactive"; }
systemctl --user is-active -q agent-fleet-www.service  || { escalate red; note "www service down"; }

# ---- 5. store sanity --------------------------------------------------------
skills=$(find skills -name SKILL.md 2>/dev/null | wc -l)
[ "$skills" -gt 400 ] || { escalate red; note "store near-empty ($skills skills)"; }
dirty=$(git status --porcelain | wc -l)

# ---- 6. nodes ---------------------------------------------------------------
node_summary=""
for f in "$HD"/node-*.json; do
  [ -f "$f" ] || continue
  n=$(jget .node "$f"); a=$(age_h "$f"); h=$(jget .store_head "$f")
  behind=$(jget .behind_origin "$f"); conform=$(jget .conformant "$f")
  [ -z "$n" ] && continue
  node_summary="${node_summary}${n} (${a}h"
  [ "$behind" = "true" ] && { node_summary="${node_summary}, behind"; escalate yellow; note "node $n store behind origin"; }
  [ "$conform" = "false" ] && { node_summary="${node_summary}, non-conformant"; escalate yellow; note "node $n skills differ from store"; }
  node_summary="${node_summary}) "
  if [ "$a" -gt 30 ]; then escalate red; note "node $n silent ${a}h"
  elif [ "$a" -gt 8 ]; then escalate yellow; note "node $n quiet ${a}h"; fi
done

# ---- 7. messaging -----------------------------------------------------------
last_sha=$(cat "$STATE/last-notified-sha" 2>/dev/null || echo "")
last_color=$(cat "$STATE/last-color" 2>/dev/null || echo "")
last_msg=$(cat "$STATE/last-msg-ts" 2>/dev/null || echo 0)
msg=""; add() { printf -v msg '%s%s\n' "$msg" "$1"; }
new_sha=""
if [ -n "$head" ] && [ "$head" != "$last_sha" ]; then
  add "🔄 agent-fleet store updated ($head): $(git log -1 --format=%s | head -c 120)"
  add "skills: $skills · node(s): ${node_summary:-none reporting yet}"
  new_sha="$head"
fi
if [ "$color" != "$last_color" ]; then
  case "$color" in
    green) add "🟢 agent-fleet recovered — all green (sync ${sync_age}h ago, $skills skills, node(s): ${node_summary:-none})" ;;
    yellow) add "🟡 agent-fleet: $issues" ;;
    red) add "🔴 agent-fleet: $issues" ;;
  esac
fi
if [ -z "$msg" ] && [ "$color" = green ] && [ $(( now - last_msg )) -gt 86400 ]; then
  add "🟢 agent-fleet daily check — all green. Sync ${sync_age}h ago · $skills skills · node(s): ${node_summary:-none}"
fi
send_state="ok"
if [ -n "$msg" ]; then
  printf '%b' "$msg"
  if tg "$(printf '%b' "$msg")"; then
    echo "$now" > "$STATE/last-msg-ts"
    [ -n "$new_sha" ] && echo "$new_sha" > "$STATE/last-notified-sha"
    log "notified[$color]: $(printf '%b' "$msg" | head -n1)"
  else
    send_state="FAILED"; note "telegram not delivered — press START in @Astral_Hermes_Alerts_bot"
    [ "$color" = green ] && escalate yellow
  fi
fi
echo "$color" > "$STATE/last-color"

# ---- 8. status.json for the web UI ------------------------------------------
jq -n --arg ts "$(date -Iseconds)" --arg color "$color" --arg issues "${issues:-none}" \
   --arg head "${head:-?}" --arg origin "${origin_head:-?}" --argjson skills "${skills:-0}" \
   --arg sync_age "${sync_age:--}" --argjson dirty "${dirty:-0}" --arg send "$send_state" \
   --arg nodes "${node_summary:-none}" \
   '{ts:$ts, color:$color, issues:$issues, head:$head, origin_main:$origin, skills:$skills,
     sync_age_h:$sync_age, dirty_files:$dirty, telegram:$send, nodes:$nodes}' > "$STATUS.tmp" \
   && mv "$STATUS.tmp" "$STATUS"
log "check: color=$color dirty=$dirty tg=$send_state ${issues}"
# 5-day retention
cut=$(date -d '-5 days' +%Y-%m-%d)
awk -v c="$cut" '$1 >= c' "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"

[ "$color" = green ] && exit 0 || exit 1
