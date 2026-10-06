#!/usr/bin/env bash
# install.sh — agent-fleet orchestrator.
# One-liner: curl -fsSL https://harness.jitinnair.com/install.sh | bash
# Re-executes itself from disk so interactive prompts work under a pipe (R6).
set -u

# If stdin is a pipe (curl|bash), re-exec from a temp file.
if [ ! -t 0 ] && [ -z "${AF_REEXEC:-}" ]; then
  tmp="$(mktemp /tmp/af-install.XXXXXX.sh)"
  cat > "$tmp"
  export AF_REEXEC=1
  exec bash "$tmp" "$@" </dev/null
fi

AF_DIR="${AF_DIR:-}"
# Locate repo: env override > script's own dir (if it looks like the repo) > ~/agent-fleet
if [ -z "$AF_DIR" ]; then
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -d "$here/harness" ] && [ -d "$here/skills" ]; then AF_DIR="$here"; else AF_DIR="$HOME/agent-fleet"; fi
fi
export AF_DIR
export AF_DRY_RUN="${AF_DRY_RUN:-0}"
AF_REPO_URL="${AF_REPO_URL:-jitin-neutrinos/agent-fleet}"

# ---------- TUI primitives ----------------------------------------------------
# Neutrinos Blue brand + 256-color supports. Animation only on a real terminal;
# piped output gets clean static lines (no cursor games, no spinner noise).
if [ -t 1 ]; then
  B="\033[38;5;33m"; BB="\033[1;38;5;33m"; W="\033[97m"; G="\033[38;5;46m"
  R="\033[38;5;203m"; D="\033[90m"; BR="\033[1m"; X="\033[0m"
  ANIM=1
else
  B=""; BB=""; W=""; G=""; R=""; D=""; BR=""; X=""
  ANIM=0
fi
b()    { printf "${B}%s${X}" "$1"; }
bold() { printf "${BB}%s${X}" "$1"; }
dim()  { printf "${D}%s${X}" "$1"; }
okc()  { printf "${G}%s${X}" "$1"; }
errc() { printf "${R}%s${X}" "$1"; }

# The fleet mark: a terminal-pixel "lightning through a ring" — speed + motion,
# drawn once through a brightness ramp (ascii-animation density reveal).
AF_LOGO=(
"      ▄▄▄▄▄▄▄▄▄▄▄▄      "
"   ▄▄▀▀░░░░░░░░░░▀▀▄▄   "
"  ▄▀░░░░░░▄▄█▄░░░░░░▀▄  "
" ▄▀░░░░░▄██▀ ▀██▄░░░░▀▄ "
" █░░░░░██▀    ░▀██░░░░█ "
"█░░░░░██░      ░░██░░░░█"
"█░░░░██░   ▄▄▄▄   ░██░░░█"
"█░░░██░   ██████   ░██░░█"
" █░░██░   ▀████▀   ░██░█ "
" ▀▄░▀██▄   ░░░░   ▄██▀▄▀ "
"  ▀▄░░▀███▄▄▄▄▄███▀░░▄▀  "
"   ▀▀▄▄░░░░░░░░░░▄▄▀▀   "
"      ▀▀▀▀▀▀▀▀▀▀▀▀      "
)
RAMP=" ░▒▓█"

hide_cursor() { [ "$ANIM" = 1 ] && printf '\033[?25l'; }
show_cursor() { printf '\033[?25h'; }

# Reveal the mark: repaint the block in place through the density ramp, ~20fps.
reveal_logo() {
  [ "$ANIM" = 1 ] || { for r in "${AF_LOGO[@]}"; do printf "${B}%s${X}\n" "$r"; done; return; }
  hide_cursor
  local width; width=$(maxlen)
  local steps=6
  for ((s=1; s<=steps; s++)); do
    local level=$(( (s * (${#RAMP} - 1)) / steps ))
    [ "$s" -gt 1 ] && printf '\033[%dA' "${#AF_LOGO[@]}"
    for r in "${AF_LOGO[@]}"; do
      local out="" ch
      for ((i=0; i<${#r}; i++)); do
        ch="${r:i:1}"
        if [ "$ch" = " " ] || [ "$level" -ge $((${#RAMP} - 1)) ]; then
          out+="$ch"
        else
          out+="${RAMP:level:1}"
        fi
      done
      printf '\033[2K'${B}'%s'${X}'\n' "$out"
    done
    sleep 0.05
  done
  show_cursor
}

maxlen() {
  local m=0 r
  for r in "${AF_LOGO[@]}"; do [ "${#r}" -gt "$m" ] && m=${#r}; done
  echo "$m"
}

# Progress line that animates in place on a TTY, prints once when piped.
step() { printf '  %s %s\n' "$(b '▸')" "$(dim "$1")"; }
step_ok() { printf '  %s %s\n' "$(okc '✓')" "$1"; }
step_fail() { printf '  %s %s\n' "$(errc '✗')" "$1"; }

hr() { printf '  '; repeat_char '─' 54; echo; }
repeat_char() { local c="$1" n="$2" s=""; for ((i=0;i<n;i++)); do s+="$c"; done; printf '%s' "$s"; }

af_log()  { printf '[af] %s\n' "$*"; }
af_die()  { show_cursor; printf '[af:error] %s\n' "$*" >&2; exit 1; }

# ---------- banner ------------------------------------------------------------
printf '\n'
reveal_logo
printf '\n'
printf '  %s   %s\n' "$(bold 'agent-fleet')" "$(dim 'one fleet · every harness')"
printf '  %s\n' "$(dim 'skills · plugins · MCPs · sync · repair')"
printf '\n'
printf '  %s %s\n' "$(dim 'repo')" "$AF_REPO_URL"
printf '  %s %s\n' "$(dim 'target')" "$AF_DIR"
[ "$AF_DRY_RUN" = "1" ] && printf '  %s\n' "$(errc 'DRY RUN — no changes will be made')"
printf '\n'

# ---------- 1. Preflight: git + clone/fetch -----------------------------------
command -v git >/dev/null || af_die "git is required. Install git first."
# A non-empty AF_DIR without .git (e.g. a pre-seeded or previously half-cloned tree):
# move it aside and clone fresh, so git metadata is always present for future pulls.
if [ -d "$AF_DIR" ] && [ ! -d "$AF_DIR/.git" ] && [ -n "$(ls -A "$AF_DIR" 2>/dev/null)" ]; then
  mv "$AF_DIR" "${AF_DIR}.bak.$(date +%Y%m%d%H%M%S)"
  step "existing non-git copy moved aside (kept as backup)"
fi
if [ ! -d "$AF_DIR/.git" ]; then
  step "cloning $AF_REPO_URL -> $AF_DIR"
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    gh repo clone "$AF_REPO_URL" "$AF_DIR" >/dev/null 2>&1 || af_die "gh clone failed"
  elif ls "$HOME"/.ssh/id_* >/dev/null 2>&1 && ssh -T git@github.com -o StrictHostKeyChecking=accept-new 2>&1 | grep -q "successfully authenticated"; then
    git clone "git@github.com:${AF_REPO_URL}.git" "$AF_DIR" >/dev/null 2>&1 || af_die "ssh clone failed"
  else
    printf '  %s GitHub PAT with repo scope (used once, then scrubbed): ' "$(b '·')"
    IFS= read -rs pat; echo
    [ -n "$pat" ] || af_die "no gh, no ssh key, no PAT — cannot clone private repo"
    git clone "https://x-access-token:${pat}...git" "$AF_DIR" >/dev/null 2>&1 || af_die "https clone failed"
    git -C "$AF_DIR" remote set-url origin "https://github.com/${AF_REPO_URL}.git"
    step_ok "PAT scrubbed from .git/config"
  fi
else
  if [ "$AF_DRY_RUN" != "1" ]; then
    # timeout: a hung credential helper (locked keyring) must never freeze the installer
    GIT_TERMINAL_PROMPT=0 timeout 25 git -C "$AF_DIR" pull --ff-only >/dev/null 2>&1 && step_ok "repo up to date" || step "repo pull skipped — continuing with existing copy"
  fi
fi

# shellcheck source=lib/common.sh
source "$AF_DIR/lib/common.sh"

# ---------- 2. Detect harnesses ----------------------------------------------
printf '\n'
printf '  %s\n' "$(bold 'Harnesses on this machine')"
hr
mapfile -t DETECTED < <(detect_harnesses)
for d in "${DETECTED[@]}"; do
  IFS=$'\t' read -r n v <<< "$d"
  printf '  %s %-14s %s\n' "$(okc '◆')" "$(b "$n")" "$(dim "$v")"
done
if [ "${#DETECTED[@]}" -eq 0 ]; then
  af_die "no harnesses detected (hermes/claude/opencode/gemini/antigravity)"
fi
printf '\n'

# ---------- 3. Run per-harness legs -------------------------------------------
export AF_MANIFEST_DIR AF_MANIFEST_TMP
for d in "${DETECTED[@]}"; do
  IFS=$'\t' read -r n _ <<< "$d"
  printf '\n  %s\n' "$(bold "── $n ──────────────────────────────")"
  bash "$AF_DIR/harness/$n.sh" || step_fail "$n leg returned non-zero (continuing)"
done

# ---------- 3b. Rulebooks: tool-router mandate (store requirement) ------------
bash "$AF_DIR/rules/install-rulebooks.sh" || step_fail "rulebook leg returned non-zero (continuing)"

# ---------- 4. Manifest --------------------------------------------------------
versions='{}'
for d in "${DETECTED[@]}"; do
  IFS=$'\t' read -r n v <<< "$d"
  versions="$(printf '%s' "$versions" | jq --arg n "$n" --arg v "$v" '. + {($n): $v}')"
done
af_manifest versions "$versions"
af_manifest_write

# ---------- 5. Summary ---------------------------------------------------------
printf '\n'
printf '  %s\n' "$(bold 'Install complete')"
hr
for d in "${DETECTED[@]}"; do
  IFS=$'\t' read -r n _ <<< "$d"
  printf '  %s %s\n' "$(okc '✓')" "$n"
done
hr
printf '  %s %s\n' "$(dim 'manifest')" "${AF_MANIFEST:-$HOME/agent-fleet/state/manifest.json.<hostname>}"
printf '  %s\n' "$(dim 'restart each harness to pick up skills/MCPs · re-run to repair')"
printf '  %s %s\n' "$(dim 'store status')" "https://harness.jitinnair.com/ (browse the fleet · admin: /status)"
# Observability: report this node to the master (best-effort; needs node config)
if [ -x "$AF_DIR/health/node-report.sh" ]; then
  bash "$AF_DIR/health/node-report.sh" 2>/dev/null || true
fi
printf '\n'
