# demo-recorder skill

Use the bundled `pagecast` MCP server (installed under `vendor/pagecast/`) to record any web app as a GIF or video.

## MCP server command

```
node <install-dir>/vendor/pagecast/src/index.js --headless
```

Environment:
- `RECORDING_OUTPUT_DIR` — where `.gif`/`.mp4`/`.webm` land (default `~/demo-recordings`)
- `AUTH_DIR` — where login sessions are saved (default `<install-dir>/auth`)

## 9 tools

- `login_session` — opens a headed browser once so a human signs in; saves storageState to `auth/<name>.json`. Credentials never touch the model.
- `record_page` — start recording a URL; pass the saved session name to open already-authenticated.
- `interact_page` — click / hover / type / press / select / scroll / navigate; draws a human-like cursor (SVG arrow + click ring, bezier glide) on every action.
- `stop_recording`
- `convert_to_gif` — two-pass palette ffmpeg.
- `convert_to_mp4`
- `record_and_gif` — combined convenience call.
- `list_recordings`

## Workflow

1. One-time per app: `login_session` → the user signs in by hand in the headed browser.
2. `record_page` with that session name (storageState) — page opens already logged in.
3. `interact_page` with narrative pacing: wait 1–2 s between actions so the demo reads well; use explicit `wait` for spinners/animations.
4. `stop_recording`.
5. `convert_to_gif` (10–12 fps, 640–800 px wide is the sweet spot for UI demos). Then optionally `convert_to_mp4` for smooth playback.

## GIF/MP4 quality guidance

- 10–15 fps is enough for UI demos; higher wastes bits.
- 64–128 palette colors (the bundled two-pass ffmpeg does this) — near-lossless for UI, tiny files.
- Keep demos under 10 s; split into multiple short GIFs instead of one long one.
- Fade-in tip: `ffmpeg -i in.webm -vf "fade=in:st=0:d=0.6:color=black" out.webm` before converting, for a gentle black intro.

## Claude Code plugin layout (this repo)

- `.claude-plugin/plugin.json` — plugin metadata
- `skills/demo-recorder/SKILL.md` — this file
- `vendor/pagecast/` — the fork (npm deps installed, chromium pre-installed by postinstall)
- `MCP server` — `node vendor/pagecast/src/index.js --headless`
