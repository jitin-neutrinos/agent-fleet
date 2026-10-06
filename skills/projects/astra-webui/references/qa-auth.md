# Dashboard QA: session auth + browser-injection recipe

The login form POST is `/auth/password-login` (JSON `{username, password, provider}`) — NOT a form-post to `/login` (405) and NOT Basic auth. Provider id comes from `GET /api/auth/providers` (currently `basic`). The password lives in `~/.hermes/.env` as `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` (env wins over config.yaml; config carries only username + ttl). `scratch/astra-credentials.txt` holds a legacy value that satisfies Basic-auth API GETs but NOT form login — verify a stored credential against the current flow before depending on it mid-build.

## Shell login → cookie jar (never echo the password)
```bash
CJ=/tmp/astra_ck.txt
PW=$(grep -E '^HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=' ~/.hermes/.env | head -1 | cut -d= -f2- | tr -d '"') && \
curl -s -o /dev/null -w '%{http_code}' -c $CJ -X POST -H 'Content-Type: application/json' \
  -d "{\"username\":\"jitin\",\"password\":\"$PW\",\"provider\":\"basic\"}" \
  http://127.0.0.1:9119/auth/password-login     # expect 200
```

## Jar parsing pitfall
curl writes session cookies as `#HttpOnly_<domain>...` lines — a naive `startswith('#')` filter silently drops exactly the cookies you need. Strip the `#HttpOnly_` prefix, then split on tabs (fields: domain, flag, path, secure, expiry, name, value).

## Browser injection (browser_exec)
1. `new_tab('http://127.0.0.1:9119/login')` + `wait_for_load()` — land on the origin pre-auth.
2. Install the console-error collector BEFORE navigating anywhere:
   `cdp('Page.addScriptToEvaluateOnNewDocument', source="window.__astraErrs=[];window.addEventListener('error',function(e){window.__astraErrs.push(String(e.message))});...")`
3. `cdp('Network.setCookie', name=..., value=..., domain='127.0.0.1', path='/')` per jar entry.
4. `goto_url('/chat')` → real session.

Access cookies are short-lived: if QA suddenly lands on `/login?next=...`, re-login and re-inject — that is session expiry, not a page regression. Don't debug the page.

## What needs the cookie (Basic auth is NOT enough)
- `GET /api/dashboard/plugins/rescan` (Basic → 401 `no_cookie`; note it is a GET — POST gives 405)
- `/dashboard-plugins/<name>/<file>` bundles (no cookie → 302 to /login)
- Plain API GETs like `/api/status` accept Basic auth — which makes it look like auth works until a rescan or bundle fetch 401s/302s.

## Sister repo (test.jitinnair.com, 127.0.0.1:3011) — different auth shape
Password lives ONLY in `%h/.config/astra-webui/env` (`ASTRA_WEBUI_PASSWORD`, 0600, never in the repo). Password-only form; login sets a signed `astra_session` cookie. Cloudflare 403s a server-side POST to the public `https://test.jitinnair.com/api/login`, so always log in against `http://127.0.0.1:3011/api/login` (same app, same secret, no CF in the path), then plant the cookie:

```python
raw = open('/path/to/cookie.txt').read().strip(); name, _, val = raw.partition('=')
cdp('Network.setCookie', name=name, value=val, domain='127.0.0.1', path='/', httpOnly=True)
goto_url('http://127.0.0.1:3011/')   # poll for .chat-composer, not a fixed sleep
```

For the public domain use `domain='test.jitinnair.com', secure=True`. App renders null while auth state is `checking` — poll for `.app-shell` / `.chat-composer` / `#password` appearing instead of asserting immediately. **A session cookie is not a password**: never type the password into a page, never ask for it in chat — mint and plant the cookie instead. Handing back "I can't verify this visually" when the secret was sitting in an env file reads as avoidance.

## Probing a live animation mid-lap
Screenshots of an in-flight animation lie — the frame you capture is wherever the animation got to, not where you asked. Probe deterministically:

- **Pause a CSS/WAAPI animation, then set the value yourself.** `el.getAnimations().forEach(a => a.pause())` sticks, and a subsequent inline write survives — this is the reliable way to park an animated element at a chosen position and screenshot it. Reset with `a.play()` + clear the inline property.
- **A rAF-driven library (motion/react) cannot be overridden this way.** It rewrites the property on its own frame loop, and on every React re-render; `setProperty(..., 'important')` does NOT win because motion assigns the property directly, replacing the whole declaration. Read and write in the SAME synchronous `js()` block so no frame can interleave, or don't fight it — measure layout instead.
- **Headless tabs freeze rAF** (no painting), so rAF animations sit frozen at their start value. `cdp('Emulation.setFocusEmulationEnabled', enabled=True)` makes them run — but then they overwrite anything you set, so enable it only when you want to watch real motion.
- **Prefer a rendered measurement to a picture.** `getBoundingClientRect` / `getComputedStyle` are current truth. A telling tell that a bar follows a path: its rect swaps orientation (e.g. 170×2 on a horizontal edge → 2×170 on a vertical one) because `offset-rotate: auto` keeps it tangent.

## React inputs under CDP
`Input.insertText` and synthetic CDP key events do not reliably reach React handlers. Drive controlled inputs with the native value setter + input event, and key handling with KeyboardEvent on the focused element:
```js
var ta = document.querySelector('.astra-composer-input');
Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta, '/');
ta.dispatchEvent(new Event('input', {bubbles:true}))
ta.focus();
ta.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true}));
```
Check `document.activeElement` before asserting keyboard behavior — focus silently lost to BODY no-ops the probe and the assertion lies.

## Viewport + motion emulation
```python
cdp('Emulation.setEmulatedMedia', features=[{"name":"prefers-reduced-motion","value":"reduce"}])
cdp('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=2, mobile=True)
cdp('Emulation.clearDeviceMetricsOverride')   # when done
```
Assert reduced-motion via `getComputedStyle` (durations clamped to `--astra-d-1`) AND layout geometry (e.g. rail bounding rect unchanged) — the block must clamp durations without deleting layout transforms.

## Live-fire QA blockers (read before polling for a rendered artifact)

- **A fresh chat opens on the landing greeting with an unanswered clarify card, and that card swallows synthetic sends.** A synthetic `KeyboardEvent` Enter lands on the card’s submit, not the composer, so no message is ever posted: turn count stays flat, the busy indicator stays true indefinitely, and the artifact you are polling for never appears — which reads exactly like a broken feature. Clear it first (answer it, or click Stop), then assert `document.querySelector('textarea').disabled === false` before sending.
- **Poll on two signals, not one.** `busy` alone is not progress. Watch *turn count change* AND *artifact presence*; flat turns + permanently busy means the send never landed, i.e. a driver problem, not a render problem.
- **A conversational prompt will not exercise a data-shaped feature.** “What did I spend this week?” against a fresh session returns prose from memory, because there is no data to render — that is correct behaviour, not a failed directive. Drive feature QA with a prompt whose ANSWER has the required shape (a comparison, a ranked list, a procedure).
- **Give live-fire a hard ceiling (~5 min), then hand off rather than loop.** Provider “Thinking” stretches plus the clarify loop above can consume a whole session without producing signal. When the ceiling hits, state plainly which layers ARE proven (unit suites, served bundle, CSS) and which is NOT (pixels), and ask the owner to eyeball it in their own app — one real message from them beats another synthetic loop. Never report an unverified visual as verified.

## Sweep pattern
Per route: `goto_url` → `wait_for_load` → ~2s settle → assert `window.__astraErrs` empty, nav rail present, content node count > 0, no stuck skeletons. Finish with the escape hatch: `?astra=off` must show the notice, the stock page, and the restored sidebar.