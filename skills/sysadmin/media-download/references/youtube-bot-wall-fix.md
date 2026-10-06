# YouTube bot-wall fix — full host recipe (kurama-core)

Symptom: `Sign in to confirm you're not a bot` / no formats from this residential IP on most videos (some pass intermittently). Three layers are jointly required; removing any one reintroduces the wall or breaks format extraction.

## Layer 1 — JS runtime + EJS challenge solver
Fedora's `yt-dlp` package does not bundle the yt-dlp-ejs solver scripts and `deno` is not installed. `~/.config/yt-dlp/config`:
```
--js-runtimes node
--remote-components ejs:github
```
(`ejs:github` auto-downloads + caches the solver from GitHub; the npm variant needs deno/bun.) Without this: `n challenge solving failed … No video formats found`.

## Layer 2 — YouTube session cookies (Brave)
Export once to a stable jar and reference it from the config:
```
yt-dlp --cookies-from-browser brave+kwallet6 --cookies ~/.config/vdloader/cookies.txt \
  --simulate --print title https://www.youtube.com/watch?v=jNQXAC9IVRw
# then add to ~/.config/yt-dlp/config:
--cookies /home/notjitin/.config/vdloader/cookies.txt
```
- MUST use the explicit `+kwallet6` suffix: agent shells have no `XDG_CURRENT_DESKTOP`, so keyring auto-detection picks BASICTEXT → `cannot decrypt v11 cookies: no key found`.
- Requires `python3-secretstorage` (dnf5 install) + unlocked KDE wallet (`kwalletd6`/`ksecretd` running).
- Brave profile: `~/.config/BraveSoftware/Brave-Browser/Default/Cookies` (NOT `~/.config/brave`).
- Refresh when walls return (YouTube rotates cookies): `~/.config/vdloader/refresh-cookies.sh`.
- These are the user's real account cookies: keep the file chmod 600, keep download volume sensible (official docs caution about account flags), revoke = log out of YouTube in Brave.

## Layer 3 — PO-token provider (bgutil)
```
docker run -d --name bgutil-provider --init -p 127.0.0.1:4416:4416 \
  --restart unless-stopped brainicism/bgutil-ytdlp-pot-provider:2.0.0
```
Plugin: release zip → `~/.config/yt-dlp/plugins/bgutil-plugin.zip` (yt-dlp loads zips directly from plugin dirs). Liveness: `curl http://127.0.0.1:4416/` → "not meant to be accessed directly" text. Real token test: `POST /get_pot` with `{"content_binding":"<videoId>"}` → `poToken`.

## Verification corpus (all were walled; all must resolve to titles)
- `watch?v=jNQXAC9IVRw` — Me at the zoo (19s, ~840 KB — best quick e2e)
- `watch?v=9bZkp7q19f0` — Gangnam Style
- `watch?v=tg2MwT5FPdY` — user's example walled video

Plain `yt-dlp --simulate --print title <url>` must succeed with NO per-command flags (the config supplies everything). On failure check, in order: config intact → `refresh-cookies.sh` → `docker ps` bgutil-provider → solver cache.

## Traps experienced
- `--cookies-from-browser edge` fails even with cookies present (docs themselves flag Edge as flaky) — use the browser the user actually uses.
- GitHub release downloads can 504 and save an HTML page as `*.zip`: validate with `unzip -t` before trusting; `file | grep zip` gives false positives because the filename itself contains "zip".
- A `--cookies`-carrying global config applies to every yt-dlp invocation on the host (fine — apps that don't pass `--ignore-config` inherit the fix for free).