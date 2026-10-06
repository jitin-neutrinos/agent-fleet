# Latency tuning — what is already optimal, and what is left

Read this before proposing streaming optimisations on kurama-core. Most obvious levers are already
pulled; re-auditing them wastes a session and invites a live-stream disruption.

## Measured baseline (re-verify, but expect exactly this)

| Layer | Observed | Verdict |
|---|---|---|
| CPU `scaling_governor` | `powersave` | **NOT a fault** — that label is normal on intel_pstate |
| CPU `energy_performance_preference` | `performance` | already optimal (this is the real knob) |
| qdisc / congestion control | `fq` / `bbr` | already optimal |
| Socket buffers | `rmem_max`/`wmem_max` = 16 MB | already optimal |
| Tailnet path | `active; direct <ip>:41641`, `tailscale ping` returns `via <ip>` | direct ~4 ms — a `via DERP(...)` result is the jitter cause; check it FIRST |
| NVIDIA persistence mode | Enabled | already optimal |
| GPU under load | P2, 2610 MHz, ~56 W at 1080p60 HEVC | healthy |
| `nvenc_latency_over_power` | default **enabled** | Sunshine already forces high power mode because NVIDIA's adaptive P-State harms low-latency streaming |
| `nvenc_preset` | default **1** (P1, fastest) | correct; raise BITRATE for quality, never the preset — higher presets add encode latency |
| `lan_encryption_mode` | default **0** | no Sunshine encryption on LAN; Tailscale/WireGuard already encrypts, so no double-encryption cost |
| Sunshine CPU weight | `CPUWeight=300` live in cgroup | 3x normal share already granted |
| KWin tearing | `allowTearing: true` | already allowed |

## Closed — do not reopen

- **`LimitNICE` / `Nice=-10` so Sunshine's `setpriority` succeeds.** The user manager's hard limit is
  `Max nice priority 0 0`, so no user unit can raise priority; only a system-level change on
  `user@1000.service` lifts it, and that needs a full logout/relogin. `CPUWeight=300` already
  delivers the priority. Cosmetic noise — say so plainly instead of chasing it.
- **KWin `LatencyPolicy`.** Not implemented in KWin 6.x despite appearing in Plasma 5 `kwinrc`
  examples (`strings /usr/lib64/libkwin.so.6 | grep -x LatencyPolicy` finds nothing). Writing it is
  an inert no-op, and `supportInformation` does not report it either way.
- **Disabling Sunshine LAN encryption.** Already off by default; nothing to gain.

## Open levers, ranked

1. **Client bitrate (Moonlight-side, no host change).** The host cannot exceed what the client asks —
   `max_bitrate=0` honours the client. ~15 Mbps at 1080p60 HEVC is conservative on a 4 ms direct LAN;
   40–80 Mbps is effectively free quality at no latency cost.
2. **Moonlight frame pacing = "Prefer lowest latency"** (V-Sync off). Reported as the single biggest
   client-side latency lever.
3. **`fec_percentage` 20 → ~5.** *Trade:* less overhead on a clean LAN, weaker loss protection when
   the tailnet path relays instead of going direct.
4. **`nvenc_vbv_increase` 0 → ~50.** *Trade:* low-latency variable bitrate improves scene-change
   quality, but risks packet loss on a link without headroom. Range 0–400 (400 = 5x frame-size cap).
5. **`nvenc_twopass` `quarter_res` → `disabled`.** *Trade:* minimum encode latency, slightly softer
   image. This is the one that matches "0 latency" literally.
6. **NVIDIA clock locking (`nvidia-smi -lgc`).** Marginal — Sunshine already forces high power mode —
   and it raises idle power and heat. Offer it; do not apply unilaterally.

Levers 3–5 are `sunshine.conf` edits, so they need a Sunshine restart: apply only when
`encoder.stats.sessionCount` is 0 (see "Is a client streaming right now?" in SKILL.md).

## Capability probes — run these instead of guessing whether a knob is reachable

- **Can a user service raise a limit at all?** Throwaway unit, nothing restarted:
  ```
  systemd-run --user --wait -q -p LimitNICE=40 /bin/sh -c 'grep -i "max nice priority" /proc/self/limits'
  ```
  Compare with the manager's own ceiling:
  `grep -i "max nice" /proc/$(pgrep -u 1000 -f 'systemd --user' | head -1)/limits`
- **What is the service actually running with?** `systemctl --user show <unit> -p Nice -p LimitNICE -p CPUWeight`,
  then read the live cgroup file under `/sys/fs/cgroup/user.slice/user-1000.slice/...` — a unit's
  configured value and the enforced value are not always the same thing.
- **Does the installed compositor implement a config key?** `strings /usr/lib64/libkwin.so.6 | grep -x '<Key>'`
  plus locating the KCM that writes it. `qdbus org.kde.KWin /KWin supportInformation` shows the
  effective state but does not report every key, so silence is not confirmation.
- **Is a client streaming right now?** `nvidia-smi --query-gpu=encoder.stats.sessionCount,encoder.stats.averageFps --format=csv,noheader`
  — re-sample before trusting a 0 fps reading.

Sources: [Sunshine configuration docs](https://docs.lizardbyte.dev/projects/sunshine/master/md_docs_2configuration.html)
(nvenc_preset, nvenc_twopass, nvenc_vbv_increase, nvenc_latency_over_power, lan_encryption_mode defaults) ·
[Moonlight+Sunshine optimisation guide](https://gist.github.com/JasSuri/fc14ff76daa0fc788a9754ddc8c8fe3e)
(preset vs bitrate, FEC 5 on LAN, frame pacing) ·
[r/MoonlightStreaming guide](https://www.reddit.com/r/MoonlightStreaming/comments/1d2ihd8/moonlightsunshine_optimisation_and_common_issues/).
