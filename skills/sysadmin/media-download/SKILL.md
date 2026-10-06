---
name: media-download
description: Use when downloading a YouTube or media file with yt-dlp.
---

# Media Downloads with yt-dlp

## Workflow

1. Check availability and pick formats: `yt-dlp -F <url>`. Read the format
   table for real IDs — never guess. High resolutions are video-only DASH
   streams; they need an audio stream merged in.
2. Download + merge in one command:
   `yt-dlp -f "<video_id>+<audio_id>" --merge-output-format mkv -o "~/Downloads/%(title)s [%(id)s].%(ext)s" <url>`
   - mkv is the safe merge container when mixing webm video + m4a audio
     (mp4 merge of that pair can fail depending on codecs).
   - `-f "bv*+ba/b"` works as a generic quality-first fallback, but pinning
     exact IDs from `-F` output is deterministic.
3. Check disk headroom first (`df -h`) for long/high-resolution videos —
   4K long-form videos run tens of GB for the video stream alone.
4. Run long downloads as a background terminal process with
   `notify=true`; poll progress via the `.part` file (`ls -lh`) rather than
   re-running yt-dlp.

## Host stack (kurama-core)

- Engine: pipx-managed **nightly** yt-dlp at `/home/notjitin/.local/bin/yt-dlp` (venv carries `curl_cffi` for browser impersonation; `yt-dlp-ejs` bundled; `secretstorage` injected for browser-cookie decryption). Update via `pipx runpip yt-dlp install -U --pre yt-dlp`; a venv recreation drops injections → re-run `pipx inject yt-dlp curl_cffi secretstorage`. Do NOT install terra's `python3-curl_cffi` (noarch, missing the compiled `_wrapper` — broken).
- Global config `~/.config/yt-dlp/config` applies to EVERY invocation (no caller uses `--ignore-config`): `--js-runtimes node`, `--remote-components ejs:github`, `--cookies ~/.config/vdloader/cookies.txt`, and `--extractor-args "generic:impersonate"` (bare form — yt-dlp's own suggested fix when a generic page hits a Cloudflare challenge).
- Cloudflare/TLS-fingerprint 403s: impersonation targets come from curl_cffi — verify with `--list-impersonate-targets`; extractors auto-impersonate when available. Prefer that over a global `--impersonate`.
- YouTube PO tokens: docker container `bgutil-provider` (`brainicism/bgutil-ytdlp-pot-provider`, `127.0.0.1:4416`, restart=unless-stopped) + its plugin zip in `~/.config/yt-dlp/plugins/`. Only relevant when the cookie path alone doesn't clear the wall.

## Pitfalls

- Ask before dropping quality: if the user names a resolution (e.g. 4K),
  verify `-F` lists it, pick the exact video+audio IDs, and if the filesize
  is enormous say the size and ETA up front rather than silently picking a
  smaller format.
- The final merged file appears only after BOTH streams finish; the
  `.<formath>.<ext>.part` file growing is normal mid-download, not a stall.
  Gauge speed by re-`stat`-ing the .part file twice ~30s apart.
- Filenames carry the video title verbatim — Unicode, emoji, and special
  characters included; quote paths in every shell command.
- Re-run `-F` if a format ID 404s; YouTube rotates available streams.
- YouTube is **fixed and working** on this host when the global setup is intact: `~/.config/yt-dlp/config` supplies `--js-runtimes node`, `--remote-components ejs:github`, and `--cookies ~/.config/vdloader/cookies.txt` (exported from Brave). Plain `yt-dlp <url>` needs no per-command flags. If `Sign in to confirm you're not a bot` / "no formats" returns: run `~/.config/vdloader/refresh-cookies.sh` (re-exports cookies; needs the KDE wallet unlocked), then retest — retries alone never clear the wall. Full rebuild recipe + verification corpus: `references/youtube-bot-wall-fix.md`.
- Cookie extraction from Brave REQUIRES the explicit keyring suffix: `--cookies-from-browser brave+kwallet6`. Agent/headless shells have no `XDG_CURRENT_DESKTOP`, so yt-dlp's keyring auto-detect falls back to BASICTEXT and dies with `cannot decrypt v11 cookies: no key found`. Needs `python3-secretstorage` installed (dnf5) + wallet unlocked. Brave's cookie DB lives at `~/.config/BraveSoftware/Brave-Browser/Default/Cookies` — not `~/.config/brave` — and Edge is not this user's browser; test the browser the user actually uses.
- Direct-file URLs on Cloudflare-fronted CDNs can 403 plain clients; the global `generic:impersonate` config line clears most (media.w3.org verified fixed). Always-working smoke URLs from this host: `download.samplelib.com/mp4/sample-5s.mp4` (single format), archive.org items (multi-format), and the mux test HLS `test-streams.mux.dev/x36xhzz/x36xhzz.m3u8`.
- `--print`/`-O` implies `--quiet`, which silently suppresses `--progress-template` output. Any wrapper that parses PROG lines (or just wants visible progress) must pass `--progress` alongside `--print` — otherwise downloads run fine for gigabytes while the caller sees 0% and concludes it is stuck.
- Name collisions cause silent false 'skips': two DIFFERENT videos can share title AND id (e.g. two `playlist.m3u8` sources both yield `playlist [playlist]`), and default no-overwrites then reports 'already downloaded' in ~1s with no new file. In any wrapper, make `-o` unique per job (append a job/row id).
- HLS downloads often report percent as `NA` (no upfront total). Never gate the whole progress update on a parsed percent — persist whichever fields parsed (COALESCE-style) and derive percent from downloaded/total when both exist; otherwise show bytes+speed only.
- TikTok `Unexpected response from webpage request` is an upstream, IP-dependent extractor breakage — don't debug locally; nightlies carry the fixes. Vimeo's web client requires a signed-in session by policy; account cookies (or `player.vimeo.com` embeds) are the only route.
