# gstreamer + NVIDIA troubleshooting on Nobara/Fedora/KDE

When `QT_MEDIA_BACKEND=gstreamer` does not produce decoding usage in `nvtop` (nvidia-smi dmon shows 0% dec), the issue is typically one of:

1. **Missing gstreamer NVIDIA plugin** — verify `rpm -qa | grep gstreamer` includes `gstreamer1-plugins-bad-freedesktop` and `gstreamer1-plugin-nvidia`. Install with:
   ```bash
   sudo dnf5 install gstreamer1-plugins-bad-freedesktop gstreamer1-plugin-nvidia -y
   ```

2. **Qt is still using ffmpeg backend** — after installing the NVIDIA plugin, verify `echo $QT_MEDIA_BACKEND` returns `gstreamer`. If not, ensure `~/.config/plasma-workspace/env/qt-media-backend.sh` exists and is executable, then log out/in.

3. **Wayland + gstreamer hardware acceleration** — on Wayland, gstreamer may fall back to software decoding. Test with `GST_DEBUG=*:3 gst-launch-1.0 playbin uri=file:///path/to/video.mp4` and check `nvtop` for decoding column. If still 0%, add `export GST_GL+VIDEODEC=nvjpeg` or switch to `x11` session temporarily to confirm the decode path.

4. **Codec not supported** — some YouTube VP9/AV1 streams require `gstreamer1-vaapi` or `gstreamer1-libav`. Install:
   ```bash
   sudo dnf5 install gstreamer1-vaapi gstreamer1-libav -y
   ```

After any of these, restart Plasma (`kscreen-doctor --quit && kscreen-doctor --start` or just log out/in) and verify decoding usage returns in `nvtop`.