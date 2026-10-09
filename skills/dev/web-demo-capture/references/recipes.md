# Recipes: web demo capture

## Headless auth for password-POST SPAs (no human login)
When the app is a password-login SPA and no human is present for pagecast's `login_session`:
1. Recon the auth flow in source first: login endpoint path, request body key, cookie name, cookie flags (Secure/SameSite matter for the storage state).
2. Authenticate with curl:
   `curl -c jar -H 'content-type: application/json' -d '{"password":"..."}' https://site/api/login` → expect `{"ok":true}`; then `GET /api/me` with the cookie to confirm.
3. Wrap the cookie in a Playwright storage-state file:
   `{"cookies":[{"name":"<cookie>","value":"<token>","domain":"<host>","path":"/","secure":true,"httpOnly":true,"sameSite":"Lax"}]}`
4. Pass the ABSOLUTE path as `storageState` to `record_page`. The response must say "authenticated session loaded" — a bare name instead resolves against the MCP's AUTH_DIR.
5. Read the password from the app's env file / service env on the host. Never place it in chat or in any skill file.

## Theme / stateful still captures via the fork's Playwright
The pagecast MCP has no screenshot tool; use its bundled Playwright directly for stills:
```js
const { chromium } = require('<fork-dir>/node_modules/playwright');
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: {width:1280,height:720}, storageState: '<abs path>' });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'networkidle' });
await page.evaluate(id => localStorage.setItem('<palette-key>', id), themeId);
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
await page.screenshot({ path: out });
```
One loop iteration per theme/state. Same pattern works for any state reachable via a localStorage key or URL parameter.

## Long agent turns: the two-take pattern
1. Take 1 (`record_page`, unauthenticated storage state so the login screen shows): waits + clicks + typing the prompt at human pace, submit, short beat, `stop_recording`.
2. Poll the app's API from outside until the turn is genuinely done: sessions endpoint with a `turn_running`-style flag; require true→false AND the artifact check (message count grew, reply payload contains the expected output marker e.g. a rendered card fence). Gate-approval first: `POST /api/gates/<id>/answer` with the approval choice for each pending gate.
3. Take 2 (`record_page` WITH the saved storage state): open the finished session, scroll/hover/click through the rendered output, `stop_recording`.
4. Merge: `ffmpeg -i take1.webm -i take2.webm` (concat filter or cut/trim segments), apply the intro fade before converting:
   `ffmpeg -i in.webm -vf "fade=in:st=0:d=1:color=black" out.webm`

## Frame verification
```
ffmpeg -y -ss <t> -i take.webm -frames:v 1 probe-<beat>.png   # one per story beat
```
Vision-check each probe: right app state, no stuck gate/modal, credential inputs masked, output actually rendered. Only then convert (`convert_to_gif` 10–15 fps / 640–800px, or `convert_to_mp4`).

## GIF/MP4 conversion
- GIF: `convert_to_gif` two-pass palette (10–15 fps, width 640–800). Verify size after; trim start blank frames with `startTime` if needed.
- MP4: `convert_to_mp4` crf 18–23 for smooth playback/sharing.
- Loop GIFs (login screens, ambient shots): cut a segment that starts and ends on the same visual state, or crossfade ends, so the loop is seamless.
