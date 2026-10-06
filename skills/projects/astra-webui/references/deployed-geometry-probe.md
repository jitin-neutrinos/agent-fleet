# Reading the DEPLOYED astra-webui geometry headlessly (playwright, cookie-minted)

This is the verification half of any visual change to astra.jitinnair.com — chat-landing welcome card, composer bars, sidebar selected states, yolo/send/stop buttons. Report MEASURED computed values, never "should be visible now".

## Auth (password never crosses chat)

```bash
set -a; . ~/.config/astra-webui/env; set +a
curl -s -o /dev/null -w "%{http_code}\n" -c $SCRATCH/astra-cookie.jar \
  --data-raw '{"username":"notjitin","password":"'"$ASTRA_WEBUI_PASSWORD"'","trustDevice":false}' \
  -H "Content-Type: application/json" http://127.0.0.1:3011/api/login
```

Cookie extraction for playwright (Netscape jar): the line containing `astra_session` is the LAST line; take `.trim().split(/\s+/).pop()`, then `ctx.addCookies([{ name: 'astra_session', value: val, url: 'http://127.0.0.1:3011' }])`.

## Probe pattern

Run the script from the repo root (`~/Work/projects/astra-webui`) — `playwright` is repo-local, NOT importable from scratch/.

```js
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
const jar = readFileSync('<scratch>/astra-cookie.jar', 'utf8').trim();
const val = jar.split('\n').pop().trim().split(/\s+/).pop();
const b = await chromium.launch();
for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844, isMobile: true }]) {
  const ctx = await b.newContext({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.isMobile });
  await ctx.addCookies([{ name: 'astra_session', value: val, url: 'http://127.0.0.1:3011' }]);
  const pg = await ctx.newPage();
  await pg.goto('http://127.0.0.1:3011', { waitUntil: 'networkidle' });
  await pg.waitForTimeout(1500);   // WebGL bg + reducers settle
  // geometry: getBoundingClientRect + getComputedStyle on the target selectors
}
await b.close();
```

## Gotchas that cost time

- **Stale logged-out tab → probe returns null for every selector.** The app silently shows a login wall when the `astra_session` value expired or the cookie didn't take. Re-mint the cookie before debugging anything else; a run of nulls is an auth symptom, not a selector bug.
- **Cache lies read as "the fix didn't work".** After building, verify the SERVED `dist/assets/index-*.css`/`js` carries the change (grep for the selector/decl) AND restart `astra-webui.service`; then in the probe use a CDP session with cache disabled:
  ```js
  const cdp = await ctx.newCDPSession(pg);
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
  ```
  Also confirm the browser bundle matches the change by fetching the live bundle text and grepping it INSIDE the page (`fetch(script.src).then(r=>r.text())`) — this catches a SPA still serving the previous chunk.
- **Concurrent-session interference is REAL**: another session may deploy or patch mid-probe. Re-check `git status`/`git diff HEAD` for the repo, re-mint the cookie, re-run the probe once before concluding failure. Uncommitted working-tree code is still SERVED after a rebuild — don't read `git show HEAD` and conclude code is missing.
- **Cookie origin must match exactly**: use `http://127.0.0.1:3011` (not `localhost`) or the cookie won't apply.
- For mobile, pass `isMobile: true` in addition to the narrow viewport — width alone doesn't flip Tailwind's `max-lg` classes.
- Transition states (focus/aria-expanded) need a settle wait (~300–400ms) after the click before reading computed values.
