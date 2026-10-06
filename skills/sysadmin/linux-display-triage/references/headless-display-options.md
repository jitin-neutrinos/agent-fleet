# Streaming with no physical panel attached

Every "stream won't start" on this host traces back to one condition: the desktop has **zero
outputs**, because KWin can only capture an output that exists. The durable fix is not a better
recovery path — it is making the zero-output state unrepresentable. Pick ONE of these.

## Options

| Approach | What it guarantees | Cost / risk |
|---|---|---|
| **EDID emulator ("dummy plug")** in a spare HDMI/DP port | The GPU ALWAYS sees a display, including at boot with the panel off | Pocket change, no root, no reboot, update-proof, and it covers the Windows dual-boot too. Its advertised modes become the desktop when the panel is off |
| **Kernel force-enable + custom EDID** `drm.edid_firmware=<conn>:edid/<file> video=<conn>:e` | Same, entirely in software | Needs root + initramfs edit + reboot; NVIDIA-specific and version-sensitive |
| **`krfb-virtualmonitor` on the live session** (what `stream-display` already drives) | A compositor-level output at the CLIENT's resolution, so streams need not match the panel | Works with zero displays, but recovery after a boot with no display is slow and racy (watchdog retries). Requires `capture = kwin` — the default `kms` capture cannot see a compositor-level output |
| **Dedicated `kwin_wayland --virtual` headless session** | Streams at boot with NO graphical login and nothing plugged in | Needs KWin >= 6.5.6 (`kwin_wayland --version`); most moving parts, but it is the appliance answer |

Default recommendation for this user: the **dummy plug** — it is the only option that needs no
root, cannot be broken by a driver update, and fixes headless streaming on both operating systems
in the dual-boot. Offer the kernel-EDID route only when buying nothing matters.

## Evaluating a display or plug: which modes does it really offer?

1. Plug it in — HDMI/DP are hot-pluggable, no reboot needed. Watch the connector flip
   `disconnected` -> `connected` and its `edid` file go from 0 bytes to 256.
2. **`/sys/class/drm/<connector>/modes` is the authoritative answer** — it lists exactly the modes
   the DRIVER accepted. Prefer it over any EDID parsing of your own.
3. Add refresh rates from `kscreen-doctor -o` (strip the ANSI escapes first — see SKILL.md).
4. `edid-report [connector]` (in `~/.local/bin`) does 2-3 plus identity and the bandwidth blocks.

## Pitfalls

- **EDID vendor OUIs are stored little-endian.** The HDMI VSDB bytes read `03 0C 00` and the HDMI
  Forum one `D8 5D C4`. Compare them as read and you will report the opposite of the truth —
  reverse the 3 bytes (`body[:3][::-1]`) before matching `000C03` / `C45DD8`. Getting this wrong
  declares "no bandwidth blocks, expect a 1080p cap" for a plug that is perfectly capable.
- **Most dummies are 16:9, and an ultrawide panel cannot be matched.** Common EDIDs carry
  1080p / 1440p / 2160p, sometimes 4096x2160; 3440x1440 is rare. So a 4K plug gives MORE pixels
  than a 3440x1440 panel but a different SHAPE — window layouts, wallpaper and panel positions all
  reflow when the user switches between panel-on and panel-off. Say this out loud before they buy.
- **State the resolution ceiling explicitly.** If the plug tops out at 4K60, then 1080p@120 is the
  only high-refresh option. Do not promise ultrawide streaming from a plug; the virtual-output path
  is what delivers client-resolution streams, and the plug is the fallback beneath it.
- **A dummy plug is a permanent second output** once installed (not just a boot-time crutch): KDE
  extends the desktop onto an invisible screen, so windows and the cursor can disappear onto it.
  Configure it out of the way rather than leaving it as a second workspace.
- **Only the panel's own modes should drive the panel.** With two outputs present, check which one
  the stream is actually capturing (`[pipewire] Streaming display '<name>'` in sunshine.log) —
  capturing the dummy instead of the panel silently changes the stream's resolution and aspect.
- **A dummy plug does not fix a link fault on the panel itself.** It changes the consequences
  (the desktop survives), not the cause. Keep diagnosing the panel's own connector separately.

## Sources

- NVIDIA force-enable + custom EDID, incl. why `drm.edid_firmware` alone does nothing on NVIDIA and
  the HDMI VSDB / Forum VSDB bandwidth requirement: <https://gist.github.com/HarryAnkers/8dbf551d66f00e8156ef4dd2b2b090a0>
- KDE virtual monitor discussion (dummy plug vs software): <https://discuss.kde.org/t/how-to-create-a-virtual-monitor-display/2725>
- `krfb-virtualmonitor` + `capture = kwin` for KDE Plasma 6 Wayland: <https://github.com/jhonsnake/sunshine-kde-virtual-display>
- Headless KWin session (`kwin_wayland --virtual`, needs >= 6.5.6): <https://docs.punktfunk.unom.io/docs/kde>
- Upstream Sunshine headless guide (X11/TwinView era — not applicable to a Wayland session): <https://docs.lizardbyte.dev/projects/sunshine/v0.23.0/about/guides/linux/headless_ssh.html>
