# desktop-recorder skill

Use the bundled scripts to record full-desktop demos with GPU Screen Recorder (NVENC), a Playwright browser driver, and FFmpeg post-processing with variable-speed editing and fade transitions.

## Scripts

All scripts live in `<install-dir>/scripts/`:

- `run-demo.sh` — orchestrator: launches GSR, runs the driver, builds the MP4
- `demo-driver.mjs` — Playwright driver: opens browser, performs login/navigation/typing via CDP + ydotool
- `build-mp4.py` — FFmpeg builder: multi-segment trim, 4x/1x speed zones, fade in/out, dark-frame anchor scan

## Prerequisites

- `gpu-screen-recorder` (NVENC h264)
- `ydotool` (OS-level keyboard/mouse)
- `ffmpeg` + `ffprobe`
- Node.js with Playwright (`npm install playwright`)
- ImageMagick `identify` (for frame brightness scanning)
- Brave browser at `/usr/bin/brave-browser`

## Environment

- `WAYLAND_DISPLAY` — Wayland display (default `wayland-0`)
- `XDG_RUNTIME_DIR` — runtime dir (default `/run/user/1000`)
- `GSR_OUTPUT` — GSR output path (default `<scratch>/gsr-raw.mkv`)
- `DEMO_OUTPUT` — final MP4 path (default `<scratch>/astra-login-demo.mp4`)

## Workflow

1. **Configure** the driver: edit `demo-driver.mjs` to set the target URL, login credentials (via vault), and the sequence of actions (navigation, typing, clicking).
2. **Run**: `bash run-demo.sh` — this launches GSR, waits for the driver to signal readiness, performs the scripted actions, then builds the MP4.
3. **Output**: a 1080p H.264 MP4 with fade-in from black, variable-speed zones (4x for thinking/tools, 1x for streaming), and fade-to-black outro.

## Post-processing (build-mp4.py)

The builder reads `timings.json` (written by the driver) to determine segment boundaries:

- **seg1 1x**: browser open → URL typed + Enter
- **seg2 1x**: login → landing → yolo toggle → query typed
- **seg3 4x**: thinking + tool execution (sped up)
- **seg4 1x**: streaming response + hold

A dark-frame anchor scan finds the true video start (first dark frame after the last bright frame), trimming any pre-window wallpaper. Fades: 0.8s black in/out.

## Key features

- **GTK dark theme**: `GTK_THEME=Adwaita:dark` + `--default-background-color=020C1BFF` for consistent dark UI
- **OS-level input**: `ydotool` for address bar typing (Ctrl+L + URL + Enter)
- **Tab-handle race fix**: polls all CDP contexts, adopts whichever tab holds the target URL, `goto` fallback
- **Jump-cut**: trims white inter-document navigation flashes
- **Dark-frame scan**: anchors video start to first truly dark frame

## Layout

```
desktop-recorder-plugin/
├── .claude-plugin/plugin.json
├── skills/desktop-recorder/SKILL.md  — this file
├── scripts/
│   ├── run-demo.sh
│   ├── demo-driver.mjs
│   └── build-mp4.py
└── RESULT.md  — verification notes from the reference run
```
