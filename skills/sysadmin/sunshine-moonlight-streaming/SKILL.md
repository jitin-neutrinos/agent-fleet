---
name: sunshine-moonlight-streaming
quisition: none
description: "Fix Sunshine/Moonlight jitter, crash loops, pairing issues."
tags: [streaming, sunshine, moonlight, wayland]
---

# Sunshine/Moonlight on kurama-core

## Setup facts
- Sunshine user service: `app-dev.lizardbyte.app.Sunshine` (`systemctl --user`).
- Binds to Tailscale IP 100.97.142.40 only (`bind_address` in ~/.config/sunshine/sunshine.conf).
- capture = kwin (pipewire). global_prep_cmd drives /home/notjitin/.local/bin/stream-display (virtual output 'Virtual-sunshine' at client res).
- Client: laptop in-neu-bl-l0518 over Tailscale.

## Crash loop 226/NAMESPACE (fixed 2026-09-09)
iGPU disabled in BIOS → /dev/dri has only card0 (NVIDIA). Old override.conf had
`InaccessiblePaths=/dev/dri/card1` and `=/dev/dri/renderD128` → namespace setup failed.
Fix: remove those two lines from ~/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d/override.conf,
`systemctl --user daemon-reload && restart`. Backups in ~/Work/scratch/.
Silver lining: pure-NVIDIA system enables DMA-BUF CUDA path.

## Jitter during animations (mitigated 2026-09-09)
Root cause: KWin 6.7 variable-rate pipewire capture — static content trickles, animations
fire up to 120 fps at the encoder in bursts (kde bug 524129; LizardByte #5195 #4843).
Mitigation in sunshine.conf:
```
minimum_fps_target = 40
nvenc_twopass = quarter_res
```
NOTE: this Sunshine build rejects `max_fps` (Unrecognized configurable option) — fps is
client-driven. Valid nvenc_twopass values: disabled | quarter_res | full_res.

## Sunshine's NVENC needs a driver the distro may not ship (2026-09-14)
Upstream builds link ffmpeg from the `LizardByte/build-deps` tag that `third-party/build-deps`
is checked out at, and that archive also supplies `nvEncodeAPI.h`. The tag decides which driver
is required: **v2026.713.132551 is NVENC API 13.0** (works on driver 595.91.07), **v2026.724.203728
and every later tag is 13.1 (needs driver >= 610)**. With a too-old driver Sunshine does not fail:
it silently encodes with `*_vulkan` instead, losing the `nvenc_*` knobs and nvidia-smi encoder
telemetry. Check the tag before blaming the driver:
```bash
find third-party/build-deps -name nvEncodeAPI.h -exec grep -m2 MINOR_VERSION {} \;
```
Rebuild recipe: `bash ~/Work/streamer/build-sunshine-nvenc.sh` (clone at the release tag, pin
build-deps one tag back, configure, build, and smoke-test that `Found HEVC encoder: hevc_nvenc`
appears). Rolling back the *driver* is not the answer -- Nobara ships no 610 branch.
Live result on this host: `~/.local/bin/sunshine-906-nvenc` (embeds `Lavc62.28.102`), source kept
at `~/Work/sunshine-nvenc-src`, wired in by a unit drop-in, packaged 906 untouched as the fallback.
Verify any Sunshine build's encoder level with `strings <binary> | grep -oE 'Lavc6[23]'`:
Lavc62 = ffmpeg 8 = NVENC 13.0, Lavc63 = ffmpeg 9 = needs driver 610.

### Three walls in that build (all handled in the script, do not rediscover)
1. **CUDA is mandatory by default** -- `CUDA not found` at `cmake/compile_definitions/linux.cmake:66`.
   Pass `-DCUDA_FAIL_ON_MISSING=OFF`. The nvenc encoder does **not** need CUDA: the capture path
   then falls back to the generic upload device (`[pipewire] using memory buffers`, same as the
   pre-upgrade working setup) and `Found ..._nvenc [nvenc]` still appears. Trade-off: no DMA-BUF
   zero-copy. A full CUDA toolkit is ~2 GB and drags driver packages -- see the dnf warning above;
   only install if zero-copy is actually wanted.
2. **glad's GL-loader generator runs with the system Python, which has no `jinja2`** -- upstream
   creates its own venv (`cmake-build-*/glad-python`, which does have jinja2) but never points the
   build rule at it, so the build dies at 3% with `ModuleNotFoundError: No module named 'jinja2'`.
   Pass `-DGLAD_SKIP_PIP_INSTALL=ON -DPython_EXECUTABLE=$BUILD/glad-python/bin/python`. The script
   pre-creates that venv with `uv venv` + `uv pip install jinja2`.
3. **The encoder smoke test must not run against the live desktop as a plain second instance** --
   it fights the running service, floods `pw.thread-loop ... iterate error -22`, dumps core before
   the encoder probe, and the build gets reported as failed even though the binary is good. Give the
   probe `port = 48989` + `stream_audio = disabled`; judge by the log, not the exit code (the
   process legitimately keeps running, so `timeout` returns 124).

### Do NOT install the CUDA toolkit to "get zero-copy" on this host
Evidence, not theory: the pre-upgrade build *had* CUDA compiled in and still logged
`[pipewire] Hybrid GPU system detected (Intel + discrete) - CUDA will use memory buffers` for every
session. Sunshine skips its DMA-BUF zero-copy route when it detects a hybrid-GPU system, and this
host is detected that way (the CPU's integrated graphics stay visible to it despite being disabled
in BIOS). So CUDA changes nothing about the capture path here -- it would cost ~2 GB, a rebuild,
and the driver-package risk above. The encoder is identical either way; only the frame hand-off
would differ, and both routes copy.

### Starved-by-a-busy-host freezes: the cgroup weight is the only usable lever
`Ping Timeout` reconnect storms correlate with host saturation (Steam shader-cache rebuilds spawn
dozens of processes), **not** with the encoder. `Nice=` and RT scheduling are unusable (2026.906
drops elevated privileges on the KWin path by design; RTKit refuses a systemd user unit), but
`CPUWeight` needs no privilege because the user manager owns that cgroup subtree, and it applies
live without dropping a stream:
```bash
systemctl --user set-property --runtime app-dev.lizardbyte.app.Sunshine.service CPUWeight=500
```
Persist it in a unit drop-in (`30-cpu-priority.conf`). It is a proportional share -- inert while the
host is idle, only bites under contention. Verify with
`cat /sys/fs/cgroup$(cat /proc/<MainPID>/cgroup | cut -d: -f3)/cpu.weight`.

### Switching to a local build without losing the packaged fallback
Never overwrite `/usr/bin/sunshine`. Drop in:
```ini
# ~/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d/20-local-nvenc-build.conf
[Service]
ExecStart=
ExecStart=/home/notjitin/.local/bin/sunshine-906-nvenc
```
The empty `ExecStart=` is required or both binaries run. Rollback = delete the drop-in,
`daemon-reload`, restart. Note a locally built binary self-reports `Sunshine version: 0.0.0-<sha>-dirty`.

## Never run a bare `dnf install` on this host without excluding nvidia
Measured 2026-09-14: installing build dependencies pulled a **pending driver upgrade** into the
transaction (userspace 595.91.07 -> 595.99.02 while the running module stayed 595.91.07). Result:
`Failed to initialize NVML: Driver/library version mismatch`, and any new GPU client breaks.
Symptoms are confusing because already-running processes keep working. Fix without a reboot by
downgrading with **explicit** version specs -- plain `dnf5 downgrade` picks the previous *repo*
version, not the version that was installed:
```bash
sudo dnf5 downgrade -y nvidia-driver-libs-595.91.07-3.fc44.x86_64 nvidia-driver-595.91.07-3.fc44 \
  libnvidia-ml-595.91.07-3.fc44.x86_64 dkms-nvidia-595.91.07-3.fc44 nvidia-kmod-common-595.91.07-3.fc44 ...
```
Then verify with `nvidia-smi --query-gpu=driver_version --format=csv` and `rpm -q`.

## The panel can stay dark with nobody streaming (F14, fixed 2026-09-14)
Sunshine does **not** log `CLIENT DISCONNECTED` when a session dies by ping timeout, so the newest
log edge can say "connected" forever. The watchdog used to short-circuit on that edge alone, so the
blanked state never got re-examined and the desk stayed dark with zero encoder sessions. The rule
now: corroborate the log edge with the encoder **count** (a level, it cannot latch) on every tick
that could act, and treat a disagreement older than `STREAM_DISPLAY_WATCHDOG_STALE_GRACE` (90s,
knob on the watchdog unit) as a stale log line rather than a transition -- in both directions, so a
live stream with a stale "idle" edge still gets blanked (privacy). Diagnose with:
```bash
stream-display-watchdog --state          # active | idle | unknown
nvidia-smi --query-gpu=encoder.stats.sessionCount --format=csv,noheader
```
`unknown` + `0` sessions + a blanked panel means this bug. Pure test entry: `--action <blanked> <edge> <enc> <disagree_age>`.

## GPU card numbering is NOT stable — any card0/card1 hardcode misdetects (fixed 2026-09-14)
Symptom: every capture of Virtual-sunshine died on frame 1 with
`Couldn't scale frame: Invalid argument` → `Could not convert image`, ~15 reconnects/sec,
while DP-5 captures passed. Started right after the 16:03 reboot.
Root cause: after that boot the iGPU enumerated as **card2** (card1=NVIDIA, card2=Intel),
but the local build's hybrid-GPU gate in `src/platform/linux/pipewire.cpp` (get_dmabuf_modifiers)
only checked /sys/class/drm/card0 and card1 for Intel vendor 0x8086. Intel was missed →
false `Pure NVIDIA system - DMA-BUF will be enabled for CUDA` → CUDA import of the virtual
output's DMA-BUF frames fails 100% of frames. The same binary worked all morning because the
pre-reboot enumeration put Intel on card0/1 → "Hybrid" → memory buffers.
Fix: detection now directory-scans /sys/class/drm/card[0-9]* for any Intel vendor.
Rebuilt via incremental `cmake --build cmake-build-nvenc --target sunshine` (~2 min, no reconfigure),
installed over ~/.local/bin/sunshine-906-nvenc (pre-fix backup: sunshine-906-nvenc.bak-carddetect).
Verify any session: journal must say `Hybrid GPU system detected` per capture (the line only
appears on the first session after restart, not at startup) and `using memory buffers` in
sunshine.log; scale errors must stay 0. Detection runs at capture setup — after ANY GPU driver
change or reboot, grep the startup log for Hybrid/Pure-NVIDIA before assuming streams are fine.

## setcap: the effective bit is file-wide, not per-capability
`setcap "cap_sys_admin=p cap_sys_nice=ep" file` is **not representable** (`VFS_CAP_FLAGS_EFFECTIVE`
covers the whole file) -- libcap rejects it with `Invalid file '...' for capability operation`, and
a later `setcap cap_sys_admin+p` silently replaces the entire set. Use a single clause. Note that
2026.906 *drops* elevated privileges on the KWin path by design, so `setpriority failed for nice`
warnings persist even with `cap_sys_nice=ep`; the intended mechanism is RTKit, which refuses a
systemd **user** unit (its cgroup is not a logind session). Cosmetic -- do not chase it.

## F15: resume re-blank races the session's own capture (fixed 2026-09-15)
After a Ping Timeout, stream-display "on" (undo) restores DP-5, Sunshine starts the
next session, and the watchdog's OLD blank gate (connection age >= BLANK_GRACE=8s)
fired into that churn -- re-blanking while the session's kwingrab was racing the same
output change. Result: capture locked onto DP-5 @3440x1440 for ~45s (measured 12:17).
Fix in stream-display-watchdog: the blank path now requires the OUTPUT-SET HASH to be
unchanged for SETTLE seconds (STREAM_DISPLAY_WATCHDOG_SETTLE=15, marker file
$XDG_RUNTIME_DIR/stream-display.outset = "<hash> <epoch>", maintained on every tick
with a snapshot; hash change also re-runs screen-widget-rule, replacing the old
OUTHASH edge detection). Connection age (BLANK_GRACE) kept as a secondary gate.
Deployed to ~/.local/bin + ~/Work/streamer/deployed/; tests in test-stream-display.sh
(56 pass) cover: changed-layout defers, hash-mismatch defers, SETTLE=0 fires.
Trade-off: a genuine prep failure now re-blanks at ~15s instead of 8s past connect.

## Remaining drop source: the laptop path is DERP-relayed (measured 2026-09-15)
Host config/encoder verified good (hevc_nvenc 8-bit, kwin capture, pacing, CPUWeight).
The drops that remain are network: `tailscale status` shows in-neu-bl-l0518 as
`active; relay "blr"` and `tailscale ping --until-direct --c 40` never left DERP
(7-15ms RTT — the relay is close; loss bursts, not distance, cause the stutters).
Desktop side is traversable (netcheck: UDP true, MappingVariesByDestIP false, UPnP ok,
static IP). The office laptop can't take inbound UDP. 7d journal: 30/111 sessions ended
Ping Timeout; negotiated bitrates 7.3-15 Mbps (client throttling itself).
Fix paths in order: (1) router port-forward UDP 41641 -> 192.168.0.105 so the laptop
only needs outbound UDP; (2) allow inbound UDP 41641 on the laptop Windows firewall;
(3) self-hosted DERP in BLR if no UDP passes either way; (4) AV1 client codec as a
loss-tolerance stopgap. Bitrate should be raised client-side only after direct path.
Also observed: after a Ping Timeout, the reconnect can capture DP-5 @3440x1440 for up
 to ~45s because the prep-cmd only runs on app launch, not per reconnect (stream-display
 'undo' already restored DP-5). Guard: re-run stream-display off when output_name is
 missing at capture, or accept the glitch until drops are rare.

## 2026-09-16 re-audit: office blocker proven, home side improved
- Office laptop netcheck: UDP true but MappingVariesByDestIP=true, PortMapping empty,
  no IPv6 → office router is hard NAT; hole-punching CANNOT succeed. Windows firewall
  is CLEARED (Tailscale-In + Tailscale-UDP-41641-in rules exist and Enabled) — do not
  chase the firewall again. Office egress IP 14.195.31.98.
- Home side after static-IP→router cutover: netcheck now shows PortMapping UPnP and a
  LIVE obtained mapping (EX220-G2u, 192.168.0.1, external 122.166.219.168:39414).
  Desktop endpoint reachable; the only missing half is the office side.
- Live jitter proof: tailscale.exe ping laptop→home showed 10/139/20 ms via DERP.
- Laptop link is wired Ethernet 192.168.0.114 — never blame Wi-Fi.
- Only viable fixes: self-hosted BLR relay (Peer Relay preferred over custom derper per
  Tailscale docs) or office IT change (unlikely). Hotspot test worthless: Indian mobile
  data is also hard-NAT.
- Recon pattern for the laptop: run tailscale.exe/powershell inside WSL via lp.sh;
  streaming long output (>~15s: netcheck, ping, PS cmdlets) KILLS the SSH pipe —
  write to ~/ts-*.txt then cat in a second lp.sh call. netsh advfirewall works where
  Get-NetFirewallRule died.
Cosmetic, do not chase: setpriority nice warnings, pipewire reset/DP-5-gone pairs
(between-session output toggles), steam.png/desktop.png warnings.

## Upstream fix watch (bug 524129), scheduled since 2026-09-30
Cron `f95215b3d357` checks daily 22:00 unless delivered: does the KWin pacing fix
(nanosecond deadlines + fixed capture interval) exist in the installed kwin?
Dry-run test, interpreted against the cron output file (`---FEED---` is populated
only when grep hits):
```bash
rpm -q kwin; echo '---CHANGELOG---'; rpm -q --changelog kwin | grep -im5 -E '524129|screencast|pacing' | head -10; echo '---FEED---'; curl -s --max-time 30 https://updates.nobaraproject.org/updates.txt | grep -im5 -E 'plasma.?6\.8|kwin.*6\.8|6\.8' | head -10; echo '---EOF---'
```
Pull the curl from the sandbox first. When `---FEED---` is empty and `rpm -q kwin`
still shows < 6.8, the cron message is a no-op; the answer is already in the prompt.
Rollback: to end this watch, delete this whole `## Upstream fix watch` block at
cron f95215b3d357 — leaving it instead makes later cron prompts inherit the stale
version as their baseline.

## Verification quirks
- An empty changelog grep is normal BEFORE 6.8 and is NOT countered by any bug-fix
  BEFORE 6.8 — the trigger is the VERSION (`rpm -q kwin` >= 6.8). Same rule applies to the feed check.
- Laptop Windows firewall drops ICMP: test laptop reachability with `tailscale ping`, never `ping`.
- PipeWire capture reset warning in journal (`Forcing session reset`) = capture pipeline hiccup,
  separate from encoder issues.
- After any config edit: restart user unit, confirm new values appear in journal
  `config: 'key' = value` lines, and check for `Unrecognized` warnings.