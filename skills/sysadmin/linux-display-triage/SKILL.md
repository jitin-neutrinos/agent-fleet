---
name: linux-display-triage
description: Use when a monitor shows nothing, a Sunshine stream will not start, or the desktop has zero outputs on kurama-core.
---
# Display/monitor triage on the kurama-core Wayland host

A "dead" monitor on this host is usually a lost DisplayPort link or a stuck stream-blanking state — not broken hardware. The host streams via Sunshine with a panel-blanking system that disables the physical output during streams. The same system means a lost panel can take the STREAM down with it: diagnose both, fix both.

## Triage ladder (do in this order)

0. **Read the logs before touching anything** — the blanking system logs every decision and its failures are usually already printed verbatim:
   - `journalctl -t stream-display` (helper), `journalctl --user -u stream-display-watchdog.service` (the watchdog prints each tick's verdict), Sunshine journal for prep/capture lines.
   - A crash loop in the watchdog journal with a bash error pointing into `~/.local/bin/stream-display` means the re-blank path is dying mid-run: the stream then runs at the panel's native resolution until fixed.
1. **DRM connector status first** — this decides everything:
   ```
   for p in /sys/class/drm/card*-*/status; do echo "$p: $(cat $p)"; done
   ```
   - `disconnected` on the panel's connector = the DP/HDMI link is gone at the driver level. No software path (kscreen-doctor, KWin, restore services) can bring it back — those all require the output to still be enumerated. Go to the recovery ladder.
   - Confirm driver-level loss with the `edid` file on the connector: 0 bytes = the monitor is answering nothing. A `connected` connector with a 0-byte `edid` is a different (partial-link) fault.
   - The connector `dpms` file is read-only (0444) on this NVIDIA driver — even root cannot echo into it; do not spend a step trying. The `status` file DOES accept a write (`echo detect > .../status`) to force connector re-detection — cheap to try on every connector, but it will not recover a monitor that answers no EDID.
   - `connected` but output disabled = software state; fix with kscreen-doctor enable (step 3).
   - Also read `dpms` and `enabled` on the same connector.
2. **Query kscreen inside the user session.** A bare `kscreen-doctor` from an agent shell lacks the session env, fails with "could not connect to display", and can even core-dump. Always set the env:
   ```
   sudo -u notjitin env XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus kscreen-doctor -o
   ```
3. **Check the stream blanking state** (Sunshine prep-cmd blanks the physical panel during streams):
   - Marker `/run/user/1000/stream-display.state` exists = system still thinks the panel is intentionally blanked.
   - History: `journalctl -b | grep stream-display` — the watchdog/restore services log every blank/restore with connector name.
   - Live stream check: `nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv,noheader` — >0 = a stream is capturing; do NOT tear down the virtual output (Sunshine SIGTRAPs and coredumps).
   - Owning script: `~/.local/bin/stream-display` (off/on/status/resolve); its header documents the design. Virtual output unit: `stream-display-vm.service` (krfb-virtualmonitor, shows as `Virtual-sunshine`).
   - After ANY live-script edit, sync the repo copy: `cp ~/.local/bin/stream-display* ~/Work/streamer/deployed/` — the test suite runs the `deployed/` copies, so an unsynced fix tests the OLD code and a synced repo keeps `git` truthful. Repo docs pattern: optimization.md holds numbered findings (F#), STATUS.md is newest-wins state.
4. **Recovery ladder when the link is down** (physical steps are the user's — instruct, then re-check `/status` after each):
   1. Monitor power-cycle (off, 10s, on) — forces DP link retraining; fixes most cases.
   2. Reseat the DP cable at either end.
   3. Reboot the PC.
   Once the connector reports `connected`, the stream-display restore path lights the panel on its own — or run `stream-display on --force`.

## Restore the stream when the panel is gone (headless streaming)

The permanent fix is to guarantee the GPU ALWAYS has at least one display attached, so the
zero-output state cannot arise at all — a spare HDMI/DP port holding an EDID emulator (dummy
plug) does this for pocket change, needs no root, survives updates, and covers the Windows
dual-boot too. Options, trade-offs, and how to evaluate a plug's real capability:
`references/headless-display-options.md`.

Software-only fallback: the stream does NOT need the physical panel: a KWin virtual output works with zero real displays. `stream-display` handles this itself now — `off` falls back to virtual-only when the panel is absent (instead of refusing, which aborted Sunshine's prep-cmd and the launch), and `on` leaves the virtual output standing when there is no panel to restore onto (instead of `vm_stop`, which left KWin with zero outputs and made Sunshine fatal with "no wl_output found"). To bring the stream back up after a failure:

1. Pause the watchdog so it does not race the recovery: `systemctl --user stop stream-display-watchdog.service`.
2. Clear stale state and create the virtual output: `rm -f /run/user/1000/stream-display.state; STREAM_DISPLAY_FORCE=1 ~/.local/bin/stream-display off`. Verify with kscreen (step 2 of the ladder): `Virtual-sunshine enabled`.
3. Restart Sunshine AFTER the output exists: `systemctl --user restart app-dev.lizardbyte.app.Sunshine.service`. Sunshine's ExecStartPre runs `stream-display on`, which (headless path) now leaves the output alone.
4. Verify in `~/.config/sunshine/sunshine.log`: `Found monitor: Virtual-sunshine` and `Found H.264/HEVC/AV1 encoder` lines; the three ports listening (`ss -tlnp | grep -E '47989|47990|48010'`); `encoder.stats.sessionCount` climbs to 1 when a client connects.
5. Restart the watchdog: `systemctl --user start stream-display-watchdog.service`.

## Can software power the panel ON? (researched 2026-09-07, all paths verified live)

NO — not from the dead-link state. Verified on this host:
- KWin 6 scripting API: `KWin::Output` has DpmsMode enums and `dpmsModeChanged`/`wakeUp` signals but NO set function — a KWin script cannot request DPMS on.
- KWin D-Bus: the Plasma 5 `/org/kde/KWin` DPMS interface is gone; `/KWin` only has `activeOutputName`/`supportInformation`.
- What DOES exist on the session bus: `org.freedesktop.ScreenSaver /org/freedesktop/ScreenSaver SimulateUserActivity` (callable) — but in live testing it does NOT flip a DPMS-sleeping panel back on (dpms stays Off). The reliable soft-wake is INPUT INJECTION: `YDOTOOL_SOCKET=/tmp/.ydotool_socket ydotool key 30:1 30:0` flipped dpms Off→On within seconds (any input event wakes the panel). Socket quirk: ydotoold runs as a SYSTEM service but its socket is at `/tmp/.ydotool_socket`, NOT the `/run/user/1000/.ydotool_socket` default ydotool CLI expects — without the env var the CLI fails with "No such file or directory / check if ydotoold is running" even though the service shows active. `echo On > /sys/class/drm/*/dpms` via sudo does NOT work either (write accepted, state stays Off).
- DDC/CI power-on (`ddcutil setvcp d6 1`): the Acer ED343CUR supports D6 (01/04/05). BUT ddcutil found NO display during the dead-link incident — DP DDC rides the AUX channel, which the NVIDIA driver tears down with the link. It is only available while the connector is enumerated, i.e. exactly when it's not needed for this failure mode. Still useful for the softer "standby but linked" case.
- For true remote hard-power recovery the only option is external: smart plug on the monitor's AC + a monitor that auto-powers-on when AC returns (test the Acer's behavior). Never tried yet — proposal only.

## Remote panel off/on — mechanism RE-VERIFIED 2026-09-13 (supersedes the 2026-09-07 note)

**`kscreen-doctor --dpms off` is a SILENT NO-OP on this build (kwin 6.7.4).** It exits 0,
prints nothing, and the panel state does not change. Earlier notes here claimed it worked;
that was wrong — it was never the thing darkening the panel. Three levers were tested
end-to-end today, and only the fourth works:

| Lever | Result |
|---|---|
| `kscreen-doctor --dpms off` | exit 0, **nothing changes** (verified by read-back) |
| `kscreen-doctor output.DP-3.disable` | **REFUSED by KWin** when it would leave zero outputs: "Disabling all outputs through configuration changes is not allowed" |
| `ddcutil setvcp D6 04` (DDC power) | write accepted, monitor **re-asserts On** while the GPU drives an active signal; `getvcp D6` still reads `0x01` |
| **`kscreen-doctor output.<name>.brightness.<0-100>`** | **WORKS** — per-output DDC backlight, the same path KDE's brightness slider uses. `0` = panel dark. |

`~/.local/bin/display-power on|off|status` now drives brightness. It records the pre-off
level in `~/.cache/display-power.state` so `on` restores it, and `off` is **idempotent** —
switching off an already-dark panel must NOT record `0` as the value to restore, or `on`
restores darkness and the feature looks broken. `~/.local/bin/display-toggle` flips based on
that state and keeps its 3-per-60s spam guard. Pre-2026-09-13 DPMS versions are kept at
`display-power.bak-dpms-20260913`. Reversible both ways, and the monitor stays DDC-reachable
(never stranded) — verified by round-tripping 0 -> 65 -> 0 twice and reading `getvcp D6`.

Two traps found while implementing this, both silent failures:

- **kscreen-doctor COLOURISES its output** (ANSI escapes like `\x1b[01;32mOutput: \x1b[0;0m`),
  and `NO_COLOR=1` does NOT disable them. Any line-anchored parse (`/^Output: /`) therefore
  matches NOTHING and the status reads as permanently ON. Strip escapes first:
  `kscreen-doctor -o | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g'`. Verify a parser change by printing
  the parsed rows, not by trusting the exit code.
- **`cmd | grep -q` under `set -o pipefail` fails on SIGPIPE** — grep exits at the first match,
  the producer is killed, the pipeline returns non-zero, and an `if` silently takes the else
  branch. This inverted display-toggle's decision so it never turned the screen back on. Capture
  the output to a variable and compare in-shell (`[[ "$out" == *"state: OFF"* ]]`).

Still true from the 2026-09-07 note: during an active stream the panel is intentionally absent
and these paths do not fight the stream system; the ydotool input-injection wake remains the
fallback for a standby-but-linked panel.

### "off" is dark, not durable — and it can strand the desktop

Backlight 0 is the only working off-mechanism, but it is NOT a safe overnight state. A panel
left at brightness 0 can drop its DP link; if the box then reboots — unattended update/cron
cycles do this — it comes up with **every** connector `disconnected` and 0-byte EDID, so the
desktop has no display until someone physically touches the panel and remote "on" becomes
impossible. That defeats the whole point of remote off/on, so state this trade to the user when
they ask for it, and prefer a small non-zero backlight for long idle. The remembered restore
value survives in `display-power.state`, so the panel lights correctly once the link returns.

Separate the two states before proposing a fix — they look identical to the user and need
opposite responses:

- **Dark panel, link up**: connector `connected`, non-zero EDID, `brightness=0`. Software fixes
  it: `display-power on`.
- **No display at all**: every connector `disconnected`, 0-byte EDID, and `ddcutil getvcp D6`
  answers "Display not found" (DP DDC rides the AUX channel, which dies with the link). Nothing
  in software restores it. A machine may ALREADY have rebooted into this state — check uptime and
  the previous boot before offering "reboot it" as the fix, because a warm reboot with the panel
  dark does not recover it; only the physical ladder does.

### Driving kscreen from a script: cap every call

- **Wrap EVERY `kscreen-doctor` invocation in `timeout`.** With no outputs present it does not
  fail fast — it hangs or core-dumps ("no Qt platform plugin could be initialized"), and an
  uncapped call blocks the caller indefinitely. A status command that should take milliseconds
  blocked for 200s on exactly this. Cap the `-o` parse AND the `--dpms show` line.
- **Skip the `--dpms show` query entirely when no outputs exist** — it is meaningless there and
  it is where the hang lands.
- **Report the zero-output case in words** ("no display attached at the driver level") rather
  than printing an empty table — an empty table reads as "panel is merely dark" and hides the
  real fault, sending the next session down the wrong path.
- Counting connectors: `grep -c connected` also matches "dis**connected**" and reports every dead
  connector as alive. Match the exact field — `awk '$1=="connected"'`, or a whole-line compare
  inside a script. This is the check that decides whether recovery is physical, so a false
  "connected" is expensive.
- Deny rules match the COMMAND TEXT, so a harmless read-only probe is blocked if it merely
  contains a banned token (an `rpm -q` naming the NVIDIA driver package, for instance). When
  that happens, drop the offending token and run the rest of the diagnostic in a fresh call —
  one blocked probe must not end the investigation, and the blocked command is never retried.

## Standby control gotchas (verified live 2026-09-08)

- From an agent shell, kscreen-doctor needs the session env BEFORE any subcommand: `export WAYLAND_DISPLAY=wayland-0 XDG_SESSION_TYPE=wayland` — without it, `kscreen-doctor -o` prints NOTHING and `--dpms off` dies with 'Unable to parse arguments' (it is talking to no compositor, so arg parsing fails downstream). With env set, `--dpms` PARSES but is a NO-OP on kwin 6.7.4 (see the re-verified section below — use per-output `brightness` instead); the `output.N.dpms.off` dotted syntax is NOT supported on this build and core-dumps on malformed variants.
- Once kscreen-doctor owns DPMS state, `echo On|Off > /sys/class/drm/*/dpms` via sudo STOPS working (write accepted, state reverts to kscreen's value). All power flips must then go through kscreen-doctor; ydotool input injection remains the wake fallback.
- What wakes a DPMS-off panel: ONLY input events (ydotool key injection verified; `SimulateUserActivity` verified NOT to). OBS/stream start-stop injects no input, so a panel left off stays off through a stream session and after exit — the user relies on this (streams with the panel dark). Auto-DPMS idle timeout is disabled on this host (powermanagementprofilesrc `idleTime=0`), so the panel never flips state on its own.
- powerdevil on Plasma 6 exposes NO DPMSControl D-Bus action when the idle timeout is 0 (`busctl --user tree org.kde.org_kde_powerdevil` shows only Brightness/Button/PowerProfile/SuspendSession) — do not hunt for the Plasma 5 DPMSControl path.
- User preference: leave the panel OFF when not needed and never switch it on unprompted; a helper script `~/Applications/display-control.sh on|off|status` exists for one-command flips.
- Verifying power state from a script: read `/sys/class/drm/card1-DP-3/dpms` (fast, no session env needed), not `kscreen-doctor --dpms show`. What wakes a DPMS-off panel: ONLY input injection (`YDOTOOL_SOCKET=/tmp/.ydotool_socket ydotool key 30:1 30:0`); streams and D-Bus activity do not wake it. kscreen-doctor owns DPMS once used — raw DRM writes stop taking effect (write accepted, state reverts).

## Stream quality: stutter/jitter mid-session (distinct from "stream won't start")

When the stream RUNS but stutters, diagnose in this order — the transport path first, the app config second:
1. **Check the transport path BEFORE blaming Sunshine/MTU/encoder**: `tailscale status` (look for `relay "..."` next to the client = traffic is going through a DERP relay server, NOT direct) and `tailscale ping <client>` (look for `via DERP(...)` + `direct connection not established`). A DERP relay adds variable latency and limited bandwidth — it is the jitter source when both sites have gigabit LAN, because the stream crosses the internet, not either LAN. `tailscale netcheck` also lists per-DERP-region latency. THEN find WHY it is relayed before proposing fixes — do not default to "office firewall": run the CGNAT test from home-network-triage (compare the Airtel router's UPnP WAN IP vs `curl https://api.ipify.org`; differ + 100.64.0.0/10 = carrier-grade NAT, and the Airtel line IS CGNAT). Under CGNAT the fix ladder is IPv6 direct path (client runs `tailscale ping` ~20x, no config) → Airtel public/static IPv4 → India VPS relay; hotspot tests prove nothing when the home side is CGNAT because mobile data is hard-NAT too.
2. **MTU is usually fine**: tailscale0 = 1280 is BY DESIGN (Tailscale's own header overhead), not a fault; home LAN NICs at 1500 are normal. Do not "fix" these.
3. **Confirm NVENC is active**: sunshine.log must contain `Found H.264/HEVC/AV1 encoder: *_nvenc [nvenc]` and `nvidia-smi --query-gpu=encoder.stats.sessionCount` must be >=1 during a session.
   A newer Sunshine whose bundled ffmpeg demands a newer driver than the host ships does NOT fail —
   it silently encodes with `*_vulkan`, so the `nvenc_*` knobs and the nvidia-smi encoder telemetry
   quietly disappear while the stream still looks fine. Which driver is needed is decided by the
   `LizardByte/build-deps` tag the source tree is pinned to (NVENC API 13.0 works on the 595 driver
   branch, 13.1 needs 610+), not by the release version — and a distro packaging no 610 branch
   cannot be fixed from the driver side. Prove NVENC works at all before blaming it:
   ```
   ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=size=1280x720:rate=30 -frames:v 30 \
     -c:v h264_nvenc -f null -
   ```
   Exit 0 = GPU and driver are fine and the fault is Sunshine's bundled ffmpeg → rebuild against the
   older tag; recipe in `references/rebuilding-sunshine-with-nvenc.md`. Re-run this probe after any
   driver change, because a userspace/kernel mismatch fails it for an unrelated reason. The `cuda::cuda_t doesn't support any format other than AV_PIX_FMT_NV12` errors during startup are encoder PROBING noise — Sunshine logs "Ignore any errors mentioned above" right after; do not chase them.
4. **Sunshine binds to the tailscale IP** (`bind_address = <tailscale-ip>` in sunshine.conf): verify with `ss -tlnp | grep 100.97` and `ss -ulnp` — ports appear on the tailscale IP only, so grepping `0.0.0.0` finds nothing. UDP stream ports: 47998 video, 47999 audio, 48000 control.
5. **iperf3 between the machines needs a server on BOTH ends**: `dnf5 install iperf3` on the desktop; Windows client needs iperf3.exe from iperf.fr running `iperf3.exe -s` with firewall allowance for 5201. Keep test durations short (`-t 10`) — long foreground client runs outlive the agent terminal's command timeout and get killed mid-run with truncated results. UDP test for jitter/loss: `iperf3 -c <host> -u -b 20M -R`.
6. **Bitrate is client-requested, not host-set**: the session's real bitrate comes from the Moonlight client (log line `Streaming bitrate is <n>` in sunshine.log; observed default ~7.3 Mbps for 1080p HEVC). Fixing the path is step one; after a DIRECT connection exists, tell the user to raise the client-side bitrate (20-50 Mbps for 1080p60/1440p) — the host alone cannot improve picture quality beyond what the client asks for.

## Is a client streaming right now? (check before ANY change)

`nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv,noheader`

- **`>=1` → a client is watching; hands off.** Do not restart Sunshine, reconfigure the compositor,
  or edit display state. Every `sunshine.conf` edit takes effect only at a Sunshine restart, and that
  restart drops the connected client mid-session. Stage the change, tell the user it is staged, and
  apply it when idle — or ask first.
- **`0` → safe to restart and apply.**

Collect config changes and apply them in ONE restart, never one restart per setting, and re-check
before and after.

### The log edge can lie — the encoder COUNT is the source of truth

Sunshine does **not** log `CLIENT DISCONNECTED` when a session dies by ping timeout, so the newest
log edge can read "connected" indefinitely while the encoder is idle. A rule that trusts the log
edge alone therefore stops re-examining the blanked state and leaves the desk dark with nobody
streaming; mirrored, it can leave the desktop visible during a live stream whose "idle" edge is
stale (the worse failure — privacy). Corroborate the edge with `sessionCount` — a **level**, which
cannot latch — on every tick that could act, and treat a disagreement older than the watchdog's
`STREAM_DISPLAY_WATCHDOG_STALE_GRACE` (90s) as a stale log line rather than a transition, in BOTH
directions. Diagnosis: `stream-display-watchdog --state` reporting `unknown` together with
`sessionCount=0` and a blanked panel is exactly this bug. The decision rule is exposed pure for
tests as `stream-display-watchdog --action <blanked> <edge> <enc> <disagree_age>` — extend that
instead of reasoning about the clock.

## Latency tuning — the settled ground

This host is already tuned past the point where host-side settings reduce latency further; the
remaining levers are client-side or are explicit trade-offs. The measured baseline, the items that
are closed, the ranked open levers, and the capability probes to answer "is this knob even
reachable?" without disturbing a session are in `references/latency-tuning.md`. Read it before
proposing streaming optimisations so the whole audit is not repeated.

## The live/deployed drift trap (found 2026-09-14)

`stream-display` exists in TWO places and they are not the same file:

- production: `~/.local/bin/stream-display` — what Sunshine's `global_prep_cmd` and the watchdog run
- test target: `~/Work/streamer/deployed/stream-display` — what `test-stream-display.sh` runs by default

On 2026-09-14 they had DRIFTED: production was a 234-line version, the deployed copy 415 lines.
The deployed one carried `resolve_real()` (panel found by EDID UUID, not connector name), the E24
headless fallback, and the `--force` flag. Production had lost all three — which is exactly why a
stream refused to start with the physical panel off **while the suite still reported 37/0 green:
it was validating the other file.**

First move on any stream-start bug:
`cmp ~/.local/bin/stream-display ~/Work/streamer/deployed/stream-display`, then run the suite with
`SD=~/.local/bin/stream-display` so it tests what actually runs. After any edit, sync both ways.

## What stream-display guarantees (verify against the live file, not this summary)

- **Never refuse when the panel is absent (E24).** Sunshine aborts the whole launch when its `do`
  command fails, so refusing killed the STREAM as well as the panel. With no physical output the
  script now goes headless and still creates the client-sized virtual output.
- **The panel is found by EDID-derived UUID** (`STREAM_DISPLAY_OUTPUT_UUID`), because connector
  names are not stable — an iGPU blacklist once renumbered the same monitor `DP-5` → `DP-3`.
  `STREAM_DISPLAY_OUTPUT` pins a connector directly and skips resolution (what the tests use).
- **`on` refuses while an NVENC session is live** (exit 3) and points at `--force`. Measured
  2026-09-14: it correctly refused a teardown during a live stream at ~59 fps. That refusal is the
  feature working — not a bug to route around.
- **kscreen-doctor colourises its output even when piped**, and its exit status is worthless (0 on
  a refused apply, a missing connector, an out-of-range value). Every change must be verified by
  reading the state back.

## Pin the capture target (2026-09-14)

`sunshine.conf` needs `output_name = Virtual-sunshine`. Without it Sunshine picks the output itself
and the log shows it choosing differently inside one session — 07:16:11 captured `DP-5` at
3440x1440, 07:16:23 captured `Virtual-sunshine` at 1920x1080. With a dummy plug permanently present
there are three outputs to choose from, so an unpinned capture intermittently streams the plug's
fixed 4K mode instead of the client-sized virtual output: a resolution lock. Takes effect on the
next Sunshine restart; the virtual output does not need to exist at Sunshine startup.

## The dummy plug (installed 2026-09-14)

A generic 4K HDMI plug sits in `HDMI-A-5`: EDID name `HDP-V104`, 39 modes, max **3840x2160@60**,
**1920x1080@120**, and no 2560x1440 or 3440x1440 mode at all. It declares both the HDMI and HDMI
Forum VSDB blocks, so full bandwidth is negotiated and it is NOT capped near 1080p. Its value here
is not as a stream target — its EDID cannot match an arbitrary client — but as the guaranteed
base output so the desktop never reaches zero outputs. Inspect any connector with
`~/.local/bin/edid-report [connector]`.

### It is the screen of last resort, not a second monitor

Keep the plug **disabled while the panel is usable** and promote it only when the panel is absent
(the headless path). A disabled output keeps its connector and EDID enumerated in KWin, so the
availability guarantee costs no compositing — while an enabled 4K plug added 8.3 Mpx of work per
frame on top of the 2.1 Mpx the client actually sees, at a persisted 270% scale that also made
`screen-widget-rule` skip it. Resolve BOTH outputs by EDID uuid, never by connector name, because
the name renumbers across driver and firmware changes.

Every fallback operation must be **best-effort and non-fatal**: Sunshine aborts the whole launch
when its `do` command exits non-zero, so a cosmetic output failure must never fail
`stream-display off`. Log it and continue — the same reasoning that produced the E24 headless rule.

## Pitfalls

- **NEVER reconfigure the compositor or write KWin/display config while an encoder session is live.** `qdbus org.kde.KWin /KWin reconfigure` re-initialises the compositor, which restarts the capture pipeline: measured mid-stream it spawned a new encoder within seconds and the client dropped (`Ping Timeout` in sunshine.log) ~20s later. Check `nvidia-smi --query-gpu=encoder.stats.sessionCount` FIRST — if it is >=1, wait or ask. The stream-display NVENC interlock guards the display path only; nothing guards the compositor against you, and a call you believe is read-only is enough once it triggers a reconfigure.
- **A config key the daemon does not implement fails SILENTLY.** `LatencyPolicy` appears in Plasma 5 `kwinrc` examples but KWin 6.7 has no such key (`strings /usr/lib64/libkwin.so.6 | grep -x LatencyPolicy` → nothing), so writing it changes nothing and KWin reports no error. Before writing any config key and calling it an optimisation, prove the INSTALLED version reads it: grep the owning library for the exact key and locate the KCM that writes it. Absence of an error is not evidence the setting took effect — the same failure family as kscreen-doctor exiting 0 on a refused apply, and forum values from an older major version are a trap.
- `encoder.stats.averageFps` can read **0 while `sessionCount` is 1** for a moment right after a new encoder is created — a sampling artifact, not a dead stream (a re-sample seconds later showed a healthy 60 fps). Re-sample before acting on a 0. Only `sessionCount=0` means the stream genuinely ended; if the panel is still blanked at that point the watchdog can lag minutes, and `stream-display on` restores it (the interlock permits it because no encoder is live).
- Mid-session freeze 10-15s after connect with `[pipewire] PipeWire stream disconnected. Forcing session reset` in sunshine.log = the capture output changed under the stream (typically the physical panel dropping while DPMS/blanking interacts with the stream), forcing Sunshine to rebuild the PipeWire stream on Virtual-sunshine. Every session reset is a visible stutter — correlate the log timestamp with stream-display/journal events before touching network settings.
- When the user is remote (only access to this desktop is via Tailscale), never restart tailscaled or change its config/port/firewall while diagnosing — read-only checks only; the remote session dies with the daemon.
- `Warning: setpriority failed for nice -10/-15: Permission denied` in sunshine.log is COSMETIC — do not chase it. The systemd user manager's hard limit is `Max nice priority 0 0` (`grep -i "max nice" /proc/$(pgrep -u 1000 -f 'systemd --user' | head -1)/limits`), so NO user unit can raise priority however it is configured: `LimitNICE=` and `Nice=-10` overrides are silently clamped. Only a system-level change on `user@1000.service` lifts the ceiling, and that needs a full logout/relogin — a session restart for no real gain, because Sunshine already holds a 3x CPU weight (`CPUWeight=300`, readable at `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/app-dev.lizardbyte.app.Sunshine.service/cpu.weight`). Say plainly that it is noise. General rule: prefer cgroup controls (`CPUWeight=`) over `nice` for service priority — cgroups need no privilege, `nice` is capped by the user manager.
- Never conclude "monitor broken" from kscreen alone — kscreen only sees what DRM enumerates. DRM `disconnected` is link-level fact; kscreen "not present" can mean asleep OR link-lost.
- `set -u` bash scripts: initialize every variable unconditionally before a shared code path — a var set only inside one branch (e.g. a headless flag set only when the panel is absent) aborts the whole script with "unbound variable" when the branch is skipped. Symptom: a tool loop logs the same bash error every tick while silently never acting.
- After changing observable behavior (e.g. a failure path now succeeds instead of refusing), update the test suite's expected exit codes and state in the SAME commit — stale expectations then masquerade as regressions on the next unrelated change. Before fixing a "new" test failure, `git stash` + rerun to split "introduced now" from "stale expectation".
- systemd user units with `Environment=` lines override the unit's script's internal defaults — changing a default inside the script alone changes nothing that actually runs; edit BOTH, or `systemctl --user show <unit> -p Environment` to confirm what is live.
- Measure transitions by diffing journal timestamps (`-o short-precise`) across the event, not by user feel or by reading a test-suite run — fixture-heavy test output can be mistaken for a real transition.
- Never force-enable outputs while NVENC sessionCount > 0 — the encoder is mid-capture on the virtual output; tearing it down kills Sunshine.
- An abnormally-ended stream can leave the panel disabled AND the DP link dropped; the watchdog's restore needs the output still present, so it silently cannot fix this case — expect the physical recovery ladder.
- After ANY Sunshine restart, re-check that `Virtual-sunshine` still exists in kscreen — Sunshine's ExecStartPre runs `stream-display on`, which historically tore the virtual output down when the panel was missing, booting Sunshine into a zero-output desktop. The script now guards this, but verify the fix held rather than assuming.
- Never pipe the sudo password and command data through the same stdin (`printf 'data' | sudo -S tee file`) — sudo -S reads its PASSWORD from stdin first, so the data becomes a failed password attempt and the write silently does not happen. Use `echo "$PW" | sudo -S bash -c '... > file'` so only the password touches sudo's stdin.
- sudo ticket state does NOT persist across agent terminal calls — each call is a fresh session, so `sudo -v` in one call does not authorize the next. Feed the password (or `-S` stdin) within the same call that needs it.
- Panel identity: Acer ED343CUR 3440x1440 on the NVIDIA card. Dual-boot Windows runs its OWN Sunshine + virtual-display + panel-blanking setup (mirrors the Linux one), so a dead panel after a Windows stream or an OS switch can originate on EITHER side — ask which OS streamed last. The DRM connector name is NOT stable across boots/driver changes — resolve by EDID-derived UUID (the script does this; ask it via `stream-display resolve`).