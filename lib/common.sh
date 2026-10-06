#!/usr/bin/env bash
# lib/common.sh — shared helpers for agent-fleet install scripts.
# shellcheck shell=bash

AF_REPO="${AF_REPO:-$HOME/agent-fleet}"
AF_DRY_RUN="${AF_DRY_RUN:-0}"
AF_MANIFEST="${AF_MANIFEST:-$AF_REPO/state/manifest.json.$(hostname 2>/dev/null || echo unknown)}"
AF_MANIFEST_PUSH="${AF_PUSH_MANIFEST:-0}"

af_log()  { printf '[af] %s\n' "$*"; }
af_ok()   { printf '[af:ok] %s\n' "$*"; }
af_skip() { printf '[af:skip] %s\n' "$*"; }
af_warn() { printf '[af:warn] %s\n' "$*" >&2; }
af_die()  { printf '[af:error] %s\n' "$*" >&2; exit 1; }

af_run() {
  # af_run <description> <cmd...>  — run unless dry-run.
  local desc="$1"; shift
  if [ "$AF_DRY_RUN" = "1" ]; then af_log "[dry-run] would: $desc"; return 0; fi
  af_log "$desc"
  "$@"
}

# Command must exist AND not be a /mnt/c (Windows interop) path — R2.
af_have() {
  local p
  p="$(command -v "$1" 2>/dev/null)" || return 1
  case "$p" in /mnt/c/*|/mnt/*/Windows*) return 1 ;; esac
  return 0
}

af_version() { "$1" --version 2>/dev/null | head -1 || echo unknown; }

# Detect harnesses: prints "name<TAB>version|-" lines. Returns 1 if none found.
detect_harnesses() {
  local found=0
  if af_have hermes || [ -d "$HOME/.hermes" ]; then
    printf 'hermes\t%s\n' "$(af_have hermes && af_version hermes || echo 'config-only')"
    found=1
  fi
  if af_have claude;  then printf 'claude\t%s\n'   "$(af_version claude)";   found=1; fi
  if af_have opencode; then printf 'opencode\t%s\n' "$(af_version opencode)"; found=1; fi
  if af_have gemini;  then printf 'gemini\t%s\n'   "$(af_version gemini)";   found=1; fi
  if af_have agy || [ -d "$HOME/.gemini/antigravity" ] || [ -d "$HOME/.gemini/antigravity-cli" ]; then
    printf 'antigravity\t%s\n' "$(af_have agy && af_version agy || echo 'config-only')"
    found=1
  fi
  return $((1 - found))
}

# Hermes bases to install into: default + every profile that looks configured.
hermes_bases() {
  local base
  [ -d "$HOME/.hermes" ] && printf '%s\n' "$HOME/.hermes"
  for base in "$HOME"/.hermes/profiles/*/; do
    [ -d "$base" ] || continue
    if [ -d "${base}skills" ] || [ -f "${base}config.yaml" ]; then
      printf '%s\n' "${base%/}"
    fi
  done
}

# --- env-key plumbing -------------------------------------------------------
# af_env_get KEY — echo current value from ~/.hermes/.env or environment (values
# never printed by callers; used only to decide check-before-prompt).
af_env_get() {
  local key="$1" v=""
  if [ -f "$HOME/.hermes/.env" ]; then
    v="$(grep -m1 -E "^${key}=" "$HOME/.hermes/.env" | cut -d= -f2-)"
    # a key present but empty still counts as "set" — return the name marker
    [ -z "$v" ] && v="__SET_EMPTY__"
  fi
  [ "$v" = "__SET_EMPTY__" ] && { printf '%s' "$v"; return; }
  [ -n "$v" ] || v="${!key:-}"
  printf '%s' "$v"
}

# af_env_set_hermes KEY VALUE — upsert into ~/.hermes/.env (0600).
af_env_set_hermes() {
  local key="$1" val="$2" f="$HOME/.hermes/.env"
  [ "$AF_DRY_RUN" = "1" ] && { af_log "[dry-run] would write $key to $f"; return 0; }
  touch "$f" && chmod 600 "$f"
  if grep -qE "^${key}=" "$f"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$f"
  else
    printf '%s=%s\n' "$key" "$val" >> "$f"
  fi
}

# af_env_set_profile KEY VALUE — export line in shell profile under agent-fleet block.
af_env_set_profile() {
  local key="$1" val="$2" prof="${AF_SHELL_PROFILE:-$HOME/.bashrc}"
  [ "$AF_DRY_RUN" = "1" ] && return 0
  touch "$prof"
  # strip any previous agent-fleet block, then append fresh
  sed -i '/# >>> agent-fleet >>>/,/# <<< agent-fleet <<</d' "$prof"
  {
    printf '\n# >>> agent-fleet >>>\n'
    printf 'export %s="%s"\n' "$key" "$val"
    printf '# <<< agent-fleet <<<\n'
  } >> "$prof"
}

# af_prompt_key KEY "needed by ..." — prompt if unset; echo 1 if value collected,
# 0 if already set, empty-string-skip returns 2 (caller records skip).
af_prompt_key() {
  local key="$1" why="$2" val
  if [ -n "$(af_env_get "$key")" ]; then
    af_ok "$key already set"
    return 0
  fi
  printf '[af] %s is needed by %s' "$key" "$why"
  if [ "$AF_DRY_RUN" = "1" ]; then echo " (dry-run: would prompt)"; return 2; fi
  printf ' — enter value (empty=skip this MCP): '
  IFS= read -rs val; echo
  [ -z "$val" ] && return 2
  af_env_set_hermes "$key" "$val"
  af_env_set_profile "$key" "$val"
  export "$key=$val"
  af_ok "$key set (hermes .env + shell profile)"
  return 1
}

# --- manifest ---------------------------------------------------------------
# af_manifest FIELD JSON_VALUE — accumulate fields into a jq-built object.
AF_MANIFEST_DIR="${AF_MANIFEST_DIR:-$(mktemp -d)}"
AF_MANIFEST_TMP="${AF_MANIFEST_TMP:-$AF_MANIFEST_DIR/m}"
# NOTE: no EXIT trap here — harness scripts call af_manifest after sourcing this
# lib, and the orchestrator's af_manifest_write consumes the files before exit.
af_manifest() { printf '%s\n' "$2" > "$AF_MANIFEST_TMP.$1"; }
af_manifest_write() {
  local h="$(hostname 2>/dev/null || echo unknown)"
  [ "$AF_DRY_RUN" = "1" ] && { af_log "[dry-run] would write manifest $AF_MANIFEST"; return 0; }
  mkdir -p "$(dirname "$AF_MANIFEST")"
  {
    printf '{\n'
    printf '"hostname": "%s",\n' "$h"
    printf '"date": "%s",\n' "$(date -Iseconds)"
    local first=1 k v
    for f in "$AF_MANIFEST_DIR"/m.*; do
      [ -f "$f" ] || continue
      k="$(basename "$f")"
      k="${k#m.}"
      v="$(cat "$f")"
      [ $first -eq 1 ] || printf ',\n'
      printf '"%s": %s' "$k" "$v"
      first=0
    done
    printf '\n}\n'
  } > "$AF_MANIFEST"
  rm -f "$AF_MANIFEST_DIR"/m.*
  rm -rf "$AF_MANIFEST_DIR"
  af_ok "manifest written: $AF_MANIFEST"
  if [ "$AF_MANIFEST_PUSH" = "1" ] && [ -d "$AF_REPO/.git" ]; then
    (cd "$AF_REPO" && git add "state/manifest.json.$h" 2>/dev/null && \
     git commit -m "manifest: $h $(date -I)" --only "state/manifest.json.$h" >/dev/null 2>&1 && \
     git push >/dev/null 2>&1) || true
  fi
}
