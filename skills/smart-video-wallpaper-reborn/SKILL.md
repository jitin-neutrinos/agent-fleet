# Smart Video Wallpaper Reborn on Nobara/KDE Plasma

**Use when:** Setting up a YouTube video as lockscreen wallpaper using the `plasma-smart-video-wallpaper-reborn` KDE Plasma 6 plugin on Nobara Linux.

**Prerequisites:** Nobara 44+ with KDE Plasma 6/Wayland, NVIDIA/AMD GPU with driver support, internet access for download.

## Always-on rules (SKILL.md — never leave this session)

1. **Download with yt-dlp first** — always use `yt-dlp` (never bare `apt`/`pacman`/`pip`). On Nobara, `dnf5` is the system package manager; `yt-dlp` is the approved video downloader. [verified 2026-09-11]

2. **Never hand-install codecs/Mesa/Proton/Wine/ffmpeg/kernel** — Nobara ships patched forks. If video fails, the plugin may need gstreamer backend, not a manual install. [verified 2026-09-11]

3. **Never touch dual-boot NTFS disks** under `/run/media/notjitin/` or `/boot/efi`. The video must live on the home partition or a user-data disk, never the Windows NTFS partitions. [verified 2026-09-11]

4. **Hardware video acceleration** — always set `QT_MEDIA_BACKEND=gstreamer` in `~/.config/plasma-workspace/env/qt-media-backend.sh` for NVIDIA/AMD GPUs. Without this, video may be black or crash. [verified 2026-09-11]

5. **Lockscreen config goes in plasma-wallpaper.conf** — the `videoFile` and `videoPath` keys in `[WallpaperSmartVideo]` group under `~/.config/plasma-workspace/env/plasma-wallpaper.conf` control the video. Do not use the Plasma UI wallpaper picker for the lockscreen specifically; the env file is the authoritative source. [verified 2026-09-11]

6. **Lockscreen mode** — after setting the video path, set the lockscreen wallpaper plugin to `org.kde.smart-video-wallpaper-reborn` and mode to enabled via `kwriteconfig6`. [verified 2026-09-11]

## Procedure (step-by-step, with commands)

### Step 1 — Download the video
```bash
yt-dlp -o ~/Work/Neutrinos/community-insights-dashboard/video.mp4 "https://www.youtube.com/watch?v=S5vIFoBC-30"
```
The file will be ~9.44GiB. If the download is interrupted, it resumes automatically (`.part` extension is renamed to `.mp4` when complete).

### Step 2 — Install the Plasma 6 plugin
```bash
sudo dnf5 install plasma-smart-video-wallpaper-reborn -y
```
Package is typically already installed on Nobara. If not available, use the OBS repo or AUR.

### Step 3 — Configure the video path
```bash
kwriteconfig6 --file ~/.config/plasma-workspace/env/plasma-wallpaper.conf --group WallpaperSmartVideo --key videoFile --type string /home/notjitin/Work/Neutrinos/community-insights-dashboard/video.mp4
kwriteconfig6 --file ~/.config/plasma-workspace/env/plasma-wallpaper.conf --group WallpaperSmartVideo --key videoPath --type string /home/notjitin/Work/Neutrinos/community-insights-dashboard/video.mp4
```
Verify: `cat /home/notjitin/.config/plasma-workspace/env/plasma-wallpaper.conf` should show:
```
[WallpaperSmartVideo]
videoFile=/home/notjitin/Work/Neutrinos/community-insights-dashboard/video.mp4
videoPath=/home/notjitin/Work/Neutrinos/community-insights-dashboard/video.mp4
```

### Step 4 — Enable gstreamer hardware video acceleration
Create `~/.config/plasma-workspace/env/qt-media-backend.sh`:
```bash
#!/bin/bash
export QT_MEDIA_BACKEND=gstreamer
chmod +x /home/notjitin/.config/plasma-workspace/env/qt-media-backend.sh
```
On first login/env reload, this sets the Qt media backend to gstreamer, which correctly decodes NVIDIA (via nvidia-smi dmon) and AMD video streams.

### Step 5 — Configure lockscreen wallpaper plugin
```bash
kwriteconfig6 --group KScreenSaver --key WallpaperPlugin --type String org.kde.smart-video-wallpaper-reborn
kwriteconfig6 --group KScreenSaver --key WallpaperMode --type Int 1
```
Or via Plasma UI: Right-click Desktop → Desktop and Wallpaper → Change Wallpaper type to "Smart Video Wallpaper Reborn" → Apply. Then System Settings → Screen Locking → Configure Appearance → Change Wallpaper type to "Smart Video Wallpaper Reborn" → Apply.

### Step 6 — Restart Plasma / log out and back in
After all config changes, restart Plasma (`kshell` or log out/in) for the lockscreen to pick up the new wallpaper plugin.

## Pitfalls & troubleshooting

- **Black video or Plasma crash** — almost always the Qt media backend. Run `echo $QT_MEDIA_BACKEND`; if blank or `ffmpeg`, create/fix `qt-media-backend.sh` with `export QT_MEDIA_BACKEND=gstreamer` and restart.
- **No decoding usage in nvtop** — confirms ffmpeg backend is active instead of gstreamer. Fix Step 4.
- **Video plays on desktop but not lockscreen** — verify `kwriteconfig6 --group KScreenSaver --key WallpaperPlugin` returns `org.kde.smart-video-wallpaper-reborn` and `WallpaperMode` is `1`.
- **NTFS video path** — if video lives on `/run/media/notjitin/`, the plasma sandbox may block access. Move the video to the home partition (`~/Work/...`) instead.
- **Permission denied on video file** — ensure the user (`notjitin`) read-access to the `.mp4` file; `chmod 644` or verify no SELinux blockage (Nobara typically has SELinux off).

## References (support files)

- `references/gstreamer-nvcodec-troubleshoot.md` — if gstreamer + NVIDIA fails, steps to verify `/usr/lib/nvidia-current/` libs and `gstreamer-1.0-nvidia` package presence.
- `references/kwin-lockscreen-states.md` — KWin lockscreen state machine: when the greeter covers the virtual output, capture freezes. Correct mechanism is evdev grab of desk input (see `~/Work/streamer/desk-lock-plan.md`).
- `scripts/verify-wallpaper-setup.sh` — run this script to confirm all 5 config steps are live:
```bash
#!/bin/bash
echo "QT_MEDIA_BACKEND=$QT_MEDIA_BACKEND"
echo "videoFile=$(kreadconfig6 --file ~/.config/plasma-workspace/env/plasma-wallpaper.conf --group WallpaperSmartVideo --key videoFile 2>/dev/null || echo 'MISSING')"
echo "WallpaperPlugin=$(kreadconfig6 --group KScreenSaver --key WallpaperPlugin 2>/dev/null || echo 'MISSING')"
echo "WallpaperMode=$(kreadconfig6 --group KScreenSaver --key WallpaperMode 2>/dev/null || echo 'MISSING')"
```
Run with `bash ~/hermes-skills/smart-video-wallpaper-reborn/scripts/verify-wallpaper-setup.sh`