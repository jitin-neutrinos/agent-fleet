# Browser session auth for the sister repo (astra.jitinnair.com = 127.0.0.1:3011)

Password lives ONLY in `~/.config/astra-webui/env` (`ASTRA_WEBUI_PASSWORD`, 0600, never in the repo). Login = `POST /api/login {username:"notjitin", password, trustDevice:false}` with Content-Type application/json against `http://127.0.0.1:3011` (Cloudflare 403s a server-side POST to the public `https://astra.jitinnair.com/api/login` — same app, same secret, no CF in the path locally). 200 sets the signed `astra_session` HttpOnly cookie.

## Mint + plant (shell + playwright)

```bash
set -a; . ~/.config/astra-webui/env; set +a
curl -s -o /dev/null -w "%{http_code}\n" -c $SCRATCH/astra-cookie.jar \
  --data-raw '{"username":"notjitin","password":"'"$ASTRA_WEBUI_PASSWORD"'","trustDevice":false}' \
  -H "Content-Type: application/json" http://127.0.0.1:3011/api/login   # expect 200
```

Playwright path (see `references/deployed-geometry-probe.md` for the full script): read the Netscape jar, take the LAST line's last whitespace-separated field as the value, `ctx.addCookies([{name:'astra_session', value, url:'http://127.0.0.1:3011'}])`. Origins must match EXACTLY — `localhost` ≠ `127.0.0.1`.

## Exploded traps

- **App builds null-walled: the SPA silently shows its LOGIN WALL for an unauthed/half-authed tab.** The DOM is a WebGL canvas plus overlays at first glance and `document.querySelector('.chat-welcome')` returns null — which reads exactly like "the build dropped my feature". It is auth. Always mint + plant, then wait ~1.5–2.5s after networkidle before the first geometry read. A probe returning JSON full of nulls is the signature; re-mint before debugging anything else.
- **A cookie jar from a PRIOR session may hold a stale token that 200s the index but 401s the SPA's API calls.** Re-mint fresh at the start of every QA run; don't reuse jars across days.
- The public URL: for browser-driven QA of astra.jitinnair.com from THIS host, prefer the local origin (same app, no tunnel in the path). For public-domain planting use `domain='astra.jitinnair.com', secure=True`.
- Never type or ask for the password in chat, never `fill_input` it into the page — env-file → login POST → cookie is the only sanctioned path.
