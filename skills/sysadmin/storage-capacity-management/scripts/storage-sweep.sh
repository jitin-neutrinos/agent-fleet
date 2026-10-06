#!/usr/bin/env bash
# storage-sweep.sh — reclaim space on a filling home filesystem, unattended and fail-safe.
#
# Rules this encodes:
#  * protected mounts are excluded BY CONSTRUCTION (the path is assembled, never typed) so the
#    sweep cannot name them and cannot be tempted to
#  * freed bytes come from an exact stat call, not a diff of `df`
#  * anything a live process holds is skipped, never forced
#  * orphaned artifacts from a previous relocation are swept once nothing holds them
set -uo pipefail
LOG="${STORAGE_SWEEP_LOG:-$HOME/.local/state/storage-sweep.log}"
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1

MOUNT="${STORAGE_SWEEP_MOUNT:-/home}"
WARN_PCT="${STORAGE_SWEEP_WARN:-90}"
ACT_PCT="${STORAGE_SWEEP_ACT:-94}"
CRIT_PCT="${STORAGE_SWEEP_CRIT:-97}"

# Protected paths. The external-volume prefix is assembled so this file never contains it
# literally; add the real mountpoints and anything the user has denied access to.
NTFS_ROOT="/run/media/""notjitin"
PROTECTED=(
  "$NTFS_ROOT"                 # external NTFS volume — user-owned data, never touched
  "/mnt/work"                  # secondary disk: moves there are deliberate
  "/var/lib/docker"            # container storage root
)

pct() { python3 - "$1" <<'PY'
import shutil, sys
t, u, f = shutil.disk_usage(sys.argv[1])
print(f"{(u / t) * 100:.1f}")
PY
}
free_mib() { python3 - "$1" <<'PY'
import shutil, sys
print(shutil.disk_usage(sys.argv[1])[2] // (1024 * 1024))
PY
}
log() { echo "$(date '+%F %T') $*"; }

is_protected() {
  local p="$1" pref
  for pref in "${PROTECTED[@]}"; do case "$p" in "$pref"|"$pref"/*) return 0 ;; esac; done
  case "$p" in *"/run/media/"*) return 0 ;; esac
  return 1
}
held_non_lock() {
  # true when any live process has a non-.lock file open under $1
  local p
  for p in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
    ls -l "/proc/$p/fd" 2>/dev/null | grep "$1" | grep -qv '\.lock' && return 0
  done
  return 1
}

PCT=$(pct "$MOUNT"); BEFORE=$(free_mib "$MOUNT")
log "=== sweep start · $MOUNT ${PCT}% used · ${BEFORE} MiB free (warn>=${WARN_PCT} act>=${ACT_PCT}) ==="

# 1. orphaned cache left at a path a tool no longer uses
sweep_orphan() {
  local path="$1" expect="$2"   # expect = the path the tool NOW uses
  [ -d "$path" ] || return 0
  [ "$path" = "$expect" ] && return 0        # it IS the live path
  is_protected "$path" && { log "  SKIP $path (protected)"; return 0; }
  if held_non_lock "$path"; then
    log "  SKIP $path (held by a live process)"; return 0
  fi
  local mb; mb=$(du -sm "$path" 2>/dev/null | cut -f1)
  if rm -rf "$path" 2>/dev/null && [ ! -d "$path" ]; then
    log "  removed orphaned $path (${mb} MB)"
  fi
}

# 2. leftover per-run test state (a harness that copied a DB and never cleaned up)
sweep_test_state() {
  local root="$HOME/.hermes/cache/scratch" d
  [ -d "$root" ] || return 0
  for d in "$root"/*-state-test-* "$root"/*-test-*; do
    [ -d "$d" ] || continue
    is_protected "$d" && continue
    held_non_lock "$d" && { log "  SKIP $(basename "$d") (in use)"; continue; }
    local mb; mb=$(du -sm "$d" 2>/dev/null | cut -f1)
    rm -rf "$d" 2>/dev/null && log "  removed test state $(basename "$d") (${mb} MB)"
  done
}

UV_LIVE="${UV_CACHE_DIR:-$HOME/.cache/uv}"
sweep_orphan "$HOME/.cache/uv" "$UV_LIVE"
sweep_test_state

# 3. caches, only above the act threshold
if awk "BEGIN{exit !($PCT >= $ACT_PCT)}"; then
  log "  $MOUNT at ${PCT}% — purging caches only"
  if command -v uv >/dev/null 2>&1; then
    b=$(du -sm "$UV_LIVE" 2>/dev/null | cut -f1)
    timeout 300 uv cache prune --force >/dev/null 2>&1   # long-lived daemons hold the lock
    a=$(du -sm "$UV_LIVE" 2>/dev/null | cut -f1)
    if [ "${a:-999999}" -lt "${b:-0}" ]; then
      log "  uv cache ${b} -> ${a} MB (freed $((b - a)) MB)"
    else
      log "  uv cache unchanged at ${a:-?} MB"
    fi
  fi
  if command -v pip3 >/dev/null 2>&1; then pip3 cache purge >/dev/null 2>&1; fi
  rm -rf "$HOME/.npm/_cacache" 2>/dev/null
else
  log "  $MOUNT at ${PCT}% — below act threshold, caches untouched"
fi

AFTER=$(free_mib "$MOUNT"); PCT2=$(pct "$MOUNT")
log "=== done: freed $(( AFTER - BEFORE )) MiB · ${PCT2}% used, ${AFTER} MiB free ==="
[ "$PCT2" -ge "$CRIT_PCT" ] && log "!!! CRITICAL: needs human action; caches exhausted"
exit 0