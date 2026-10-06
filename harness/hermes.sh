#!/usr/bin/env bash
# harness/hermes.sh — install fleet into Hermes (default + configured profiles).
set -u
AF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "$AF_DIR/lib/common.sh"

command -v rsync >/dev/null || af_die "rsync required"
command -v python3 >/dev/null || af_die "python3 required (config editing)"

bases="$(hermes_bases)"
[ -z "$bases" ] && { af_skip "hermes: no ~/.hermes found"; exit 0; }

# ---- skills + plugins per base ---------------------------------------------
for base in $bases; do
  af_run "rsync skills -> $base/skills" \
    rsync -a --delete "$AF_DIR/skills/" "$base/skills/"
  af_run "rsync plugins -> $base/plugins" \
    rsync -a "$AF_DIR/plugins/hermes/" "$base/plugins/"
done

# ---- MCPs -------------------------------------------------------------------
# helpers
py_edit_cfg() { # py_edit_cfg <base> — ensure default_profile mcp entries exist? (not needed)
  :
}

hermes_mcp_present() { # name base -> 0 if already in config
  local name="$1" base="$2" cfg="$base/config.yaml"
  [ -f "$cfg" ] || return 1
  python3 - "$cfg" "$name" <<'EOF'
import sys, yaml
cfg, name = sys.argv[1], sys.argv[2]
try:
    d = yaml.safe_load(open(cfg)) or {}
except Exception:
    sys.exit(1)
sys.exit(0 if name in (d.get("mcp_servers") or {}) else 1)
EOF
}

# Answers per hermes v0.21.x mcp_config.py prompts, in order:
#   http:   "Does this server require authentication?" -> n
#           "Enable all N tools?" -> y  (saves)
#   stdio:  "Enable all N tools?" -> y
#           ("Save config anyway?" -> y if server connected but has no tools)
hermes_profile_flag() { # base -> env-prefix args for hermes (HERMES_HOME trick) as separate echo lines
  local base="$1"
  [ "$base" = "$HOME/.hermes" ] && return 0
  printf '%s\n' "HERMES_HOME=$base"
}

hermes_mcp_add() { # hermes_mcp_add <profile_flag or -> <kind> <spec> <args> <name>
  local pflag="$1" kind="$2" spec="$3" margs="$4" name="$5" answers="n\ny\n"
  [ "$kind" = "stdio" ] && answers="y\n"
  local env_prefix=()
  [ "$pflag" != "-" ] && env_prefix=("env" "$pflag")
  if [ "$kind" = "http" ]; then
    printf "$answers" | "${env_prefix[@]}" hermes mcp add --url "$spec" "$name" >/dev/null 2>&1
  else
    # shellcheck disable=SC2086
    printf "$answers" | "${env_prefix[@]}" hermes mcp add --command "$spec" --args $margs -- "$name" >/dev/null 2>&1
  fi
}

installed="[]"; skipped="[]"
add_json() { # add_json varname value
  python3 -c 'import json,sys; l=json.load(open(sys.argv[1])); l.append(sys.argv[2]); json.dump(l, open(sys.argv[1],"w"))' "$1" "$2"
}

tmpi="$(mktemp)"; tmps="$(mktemp)"; echo "[]" > "$tmpi"; echo "[]" > "$tmps"

while IFS='|' read -r name kind spec args envs notes; do
  [ -z "$name" ] && continue
  case "$name" in \#*) continue ;; esac

  # env check-before-prompt
  need_prompt=""
  if [ -n "$envs" ]; then
    IFS=',' read -ra KEYS <<< "$envs"
    for k in "${KEYS[@]}"; do
      [ -z "$k" ] && continue
      if [ -z "$(af_env_get "$k")" ]; then
        af_prompt_key "$k" "hermes MCP $name"
        rc=$?
        if [ $rc -eq 2 ]; then
          af_skip "$name: env key $k not provided"
          add_json "$tmps" "$name (env key $k not provided)"
          need_prompt=1; break
        fi
      fi
    done
  fi
  [ -n "$need_prompt" ] && continue

  if [ "$kind" = "http" ]; then
    for base in $bases; do
      pflag="$(hermes_profile_flag "$base" || true)"
      [ "$base" != "$HOME/.hermes" ] && pflag="HERMES_HOME=$base"
      if hermes_mcp_present "$name" "$base"; then af_log "$name already in $base (skip)"; continue; fi
      af_run "hermes mcp add $name ($base)" hermes_mcp_add "$pflag" http "$spec" "" "$name"
    done
    add_json "$tmpi" "$name"
  elif [[ "$spec" == MACHINE_LOCAL:* ]]; then
    bin="${spec#MACHINE_LOCAL:}"
    if [ -x "$bin" ]; then
      for base in $bases; do
        [ "$base" != "$HOME/.hermes" ] && pflag="HERMES_HOME=$base" || pflag="-"
        hermes_mcp_present "$name" "$base" && continue
        af_run "hermes mcp add $name ($base, machine-local)" \
          hermes_mcp_add "$pflag" stdio "$bin" "$args" "$name"
      done
      add_json "$tmpi" "$name"
    else
      af_skip "$name: machine-specific, not available here"
      add_json "$tmps" "$name (machine-specific binary absent)"
    fi
  else
    for base in $bases; do
      [ "$base" != "$HOME/.hermes" ] && pflag="HERMES_HOME=$base" || pflag="-"
      hermes_mcp_present "$name" "$base" && continue
      af_run "hermes mcp add $name ($base)" hermes_mcp_add "$pflag" stdio "$spec" "$args" "$name"
    done
    add_json "$tmpi" "$name"
  fi
done < "$AF_DIR/mcp/hermes.list"

af_manifest hermes_installed "$(cat "$tmpi")"
af_manifest hermes_skipped "$(cat "$tmps")"
rm -f "$tmpi" "$tmps"

skillcount="$(find "$AF_DIR/skills" -name SKILL.md | wc -l)"
af_manifest hermes_skills "$skillcount"
af_ok "hermes leg done (skills: $skillcount)"
