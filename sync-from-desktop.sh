#!/usr/bin/env bash
# sync-from-desktop.sh — desktop source-of-truth push (runs via systemd user timer).
set -u
AF_DIR="${AF_DIR:-$HOME/Work/infra/agent-fleet}"
cd "$AF_DIR" || { echo "[af-sync] no repo at $AF_DIR" >&2; exit 1; }

git pull --ff-only >/dev/null 2>&1 || echo "[af-sync] pull failed/skipped, pushing local state"

# 1. Mirror skills (hermes set is the superset)
# --exclude=.git: a skill dir that happens to be a git checkout must not create
# a nested-repo gitlink in the repo (that silently drops the skill from clones).
rsync -a --delete --exclude=.git --exclude=graphify-out/ --exclude=__pycache__/ \
  --exclude=skills/software-development/ctrader-cli/ --exclude=skills/software-development/ctrader-mcp-servers/ \
  "$HOME/.hermes/skills/" skills/

# 2. Hermes plugins
mkdir -p plugins/hermes
for p in agentmemory shell-hitl-gate slopguard; do
  [ -d "$HOME/.hermes/plugins/$p" ] && rsync -a --delete "$HOME/.hermes/plugins/$p" "plugins/hermes/"
done

# 3. Reference copies (audit aids; *.list defs stay hand-curated)
mkdir -p mcp/reference
cp "$HOME/.hermes/config.yaml" mcp/reference/hermes-config.yaml 2>/dev/null
if command -v python3 >/dev/null && python3 -c 'import yaml' 2>/dev/null; then
  python3 - <<'EOF'
import yaml, json
d = yaml.safe_load(open(f"{__import__('os').path.expanduser('~')}/.hermes/config.yaml")) or {}
json.dump(d.get("mcp_servers") or {}, open("mcp/reference/hermes-mcp.json","w"), indent=2)
EOF
fi
# claude reference: project only mcpServers, strip claude.ai OAuth entries AND all
# header/env credential values (R4/R9) — history purge after a credential landed in the reference copy.
if [ -f "$HOME/.claude.json" ] && command -v jq >/dev/null; then
  jq '{mcpServers: (.mcpServers // {}
        | del(.n8n, .Miro, .miro, .Figma, .figma, .Lovable, .lovable, .["Microsoft 365"], .ms365)
        | with_entries(.value |= (
            del(.headers)
            | if has("env") then .env = (.env | with_entries(.value = "<REDACTED>")) else . end
          )))}' \
    "$HOME/.claude.json" > mcp/reference/claude.json
  # belt and braces: refuse to ship any key-shaped string
  if grep -qE '(ctx7sk|sk-)-?-?[A-Za-z0-9]{6,}|Bearer [A-Za-z0-9]' mcp/reference/claude.json; then
    echo "[af-sync][SECURITY] credential-shaped string in claude reference — redacting file"; rm -f mcp/reference/claude.json
  fi
fi

# 4. opencode skills one-time migration to canonical path (plan §4)
if [ -d "$HOME/Work/coding-harness/config/skills" ] && [ ! -d "$HOME/.config/opencode/skills" ]; then
  mkdir -p "$HOME/.config/opencode"
  mv "$HOME/Work/coding-harness/config/skills" "$HOME/.config/opencode/skills" \
    && echo "[af-sync] migrated opencode skills to ~/.config/opencode/skills"
fi
# Once migrated, opencode is a CONSUMER mirror: refresh it FROM the store. The old
# reverse direction (opencode -> repo) silently reverted fresh hermes edits whenever
# opencode's copy was stale — the two rsyncs cancelled out and the sync reported
# "nothing to sync" (found 2026-09-14: fleet-topology.md edit bounced back).
if [ -d "$HOME/.config/opencode/skills" ]; then
  rsync -a --delete --exclude=.git skills/ "$HOME/.config/opencode/skills/"
fi

# 5. Secret scan on NEW/CHANGED content only — refuse to push if hits (belt and braces).
# Scanning the whole tree trips on caveman's own redaction TEST fixtures, so restrict
# to paths the sync actually mirrors (skills/, plugins/hermes/, mcp/reference/).
secret_hits="$(git diff --cached --name-only; git status --porcelain | awk '{print $2}')" || true
scan_paths="$(printf '%s\n' "$secret_hits" | grep -E '^(skills/|plugins/hermes/|mcp/reference/)' | sort -u | tr '\n' ' ')"
if [ -n "$scan_paths" ] && git grep -qIE '(sk-[A-Za-z0-9]{20}|ghp_[A-Za-z0-9]{20}|xox[bp]-[A-Za-z0-9-]{10}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' -- $scan_paths 2>/dev/null; then
  echo "[af-sync] SECRET-LIKE STRING STAGED — aborting push. Inspect: git grep -iE" >&2
  exit 1
fi

# 6. Commit + push only if changed
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "sync $(date -Iseconds)" >/dev/null
  git push && echo "[af-sync] pushed $(git log -1 --format=%h)"
else
  echo "[af-sync] nothing to sync"
fi

# 6b. Refresh this machine's consumer mirrors from the store. The Claude Code / Antigravity
# flat copies were only refreshed by install.sh and silently lagged between installs; the
# shared consumer script (AF_DIR pinned to this checkout) brings every present harness back
# in step. Its trailing node-report self-skips here — the master has no health.env.
# Non-fatal: a consumer failure must not fail or block the sync.
AF_DIR="$AF_DIR" bash "$AF_DIR/update.sh" || echo "[af-sync] consumer mirror refresh failed (non-fatal)"

# 7. Keep the tunnel-hosted install.sh in step (plan §5)
WWW="$HOME/scratch/agent-fleet-www"
if [ -d "$WWW" ]; then
  cp install.sh "$WWW/install.sh" && chmod 644 "$WWW/install.sh"
  sha256sum install.sh | awk '{print $1}' > "$WWW/install.sh.sha256"
  [ -f install.ps1 ] && { cp install.ps1 "$WWW/install.ps1" && chmod 644 "$WWW/install.ps1"
    sha256sum install.ps1 | awk '{print $1}' > "$WWW/install.ps1.sha256"; }
  echo "[af-sync] install.sh copied to www"
fi

# 8. Observability: stamp this successful sync, then run the health check
# (best-effort — a health problem must never block or fail the sync itself)
mkdir -p "$HOME/agent-fleet-health/state" && date +%s > "$HOME/agent-fleet-health/state/last-sync-success"
if [ -x "$AF_DIR/health/fleet-health.sh" ]; then
  bash "$AF_DIR/health/fleet-health.sh" >/dev/null 2>&1 || true
fi

# 9. Rebuild the store catalog (web UI data) so new items appear right away
python3 "$AF_DIR/catalog/build-inventory.py" >/dev/null 2>&1 || true

# 10. Reload the store server so route/logic changes go live
systemctl --user restart agent-fleet-www.service >/dev/null 2>&1 || true
