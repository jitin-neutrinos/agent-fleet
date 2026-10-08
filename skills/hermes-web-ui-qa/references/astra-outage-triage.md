# Astra 503 outage triage (proxy auth chain)

Use when astra.jitinnair.com shows "Agent backend busy (503)", chat lists/history fail to load, or astra's `/api/hx/*` routes return 503 while `/api/health` is green.

The UI banner "Agent backend busy (503)" is a LIE by design: `chats-panel.tsx` and `chat-landing.tsx` map ANY 503 from the astra proxy to that one string. The proxy 503s for at least three distinct causes — upstream login rate-limited (`{"error":"Hermes login failed: 429"}`), provider unknown (`Hermes login failed: 404`), replay-after-reauth (`{"error":"reauth"}`), proxy connect error. Never diagnose from the banner; read the body.

## Diagnosis chain (in this order)

1. **Check config size FIRST: `ls -l ~/.hermes/config.yaml`.** Healthy ≈ 22KB. Sub-1KB = a stub that dropped whole sections (`dashboard.basic_auth`, compression, streaming, moa, mcp_servers) — that alone is the diagnosis; skip the log archaeology. The `.good.` snapshots under `~/.hermes/backups/config/` show the collapse: successive stubs GROW over time (subset keys re-added one by one) while the real config is an order of magnitude bigger.
2. **Reproduce locally and read the body** (bypasses Cloudflare): `set -a; . ~/.config/astra-webui/env; set +a` → POST `http://127.0.0.1:3011/api/login` with the env password → GET `/api/hx/sessions?limit=3&order=recent` with the cookie jar. 200/200 = the incident is over or client-side; 503 + body = proceed.
3. **Reason timeline: `~/.hermes/logs/dashboard-auth.log`.** Bucket `login_failure` reasons by day/minute: `unknown_password_provider` = the `basic` auth provider is not registered (config lost `dashboard.basic_auth.username`); `rate_limited` = the shared 127.0.0.1 bucket (10 attempts/60s, `dashboard_auth/routes.py _PW_RATE_*`) is saturated; `login_success` after the break minute = different cause.

## Mechanism (why a config stub looks like "backend busy")

The dashboard's `basic` password provider (an in-tree plugin) registers ONLY when `dashboard.basic_auth.username` exists in config.yaml or `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` is set. Without it, every proxy login 404s `unknown_password_provider`; the astra proxy retries on every client request; ALL retries come from 127.0.0.1 and share ONE rate-limit bucket, so the bucket never drains and every authenticated route 503s — while `/api/health` stays green and the gateway itself is untouched.

## Fix

1. Restore the newest PRE-collapse snapshot: `cp ~/.hermes/backups/config/config.yaml.good.<ts> ~/.hermes/config.yaml` (compare sizes first; keep the stub as `config.yaml.broken-stub-<ts>` for forensics).
2. `systemctl --user restart hermes-dashboard.service`.
3. Verify: `grep "registered global provider 'basic'" ~/.hermes/logs/agent.log` (fresh timestamp), then the local chain from step 2 returns 200/200.

## Red herrings (do not chase)

- `astra-login: render_login_html not wrapped` WARNING on every dashboard boot — the login-page brand-paint plugin declining to wrap; cosmetic only, unrelated to auth.
- Gateway `/api/health` 200 and ws peers connected — proves the gateway runs, says nothing about dashboard auth.
- `astra-webui.service` restarts in journalctl — a symptom of config-reload loops, not the cause.

## Watch

The stub-writer (whatever rewrote config.yaml as a subset dump) may recur: if auth dies again with `unknown_password_provider` and the file is small again, hunt the writer — a config write that dumps a subset instead of round-tripping re-kills every dropped section on each write.
