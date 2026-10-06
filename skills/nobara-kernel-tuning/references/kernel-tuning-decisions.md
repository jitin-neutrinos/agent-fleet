# Kernel Tuning Decision Table (Nobara/CachyOS kernel hosts)

Ranked levers and the standing reject list. Evidence commands are read-only; apply steps need user go.

## Levers (apply in this order when approved)

1. **Drain stale swap** — zero risk, no reboot. Guard: `available` (free -h) > swap used and memory PSI ~ 0. Apply: `sudo swapoff -a && sudo swapon -a`.
2. **Disable zswap when zram is active** — kills double compression. Test runtime: `echo 0 | sudo tee /sys/module/zswap/parameters/enabled`; persist via `zswap.enabled=0` on kernel cmdline at next scheduled reboot (batch with other cmdline changes).
3. **sched_ext trial (`scx_lavd`)** — biggest *potential* under load; SteamOS's gameplay scheduler; handles Intel P/E hybrid; latency-criticality heuristics. Verify support: `CONFIG_SCHED_CLASS_EXT=y` + `/sys/kernel/sched_ext` present. Trial: `sudo scx_lavd` one-shot A/B under real load (reversible in seconds; kernel watchdog auto-ejects a bad scheduler back to EEVDF). Persist via `scx_loader.service` if it earns its place. Gains are workload-dependent — near-zero on an idle desktop.
4. **Take pending kernel via `nobara-sync install-updates`** at a user-chosen reboot; batch cmdline persistence into the same boot. Boot promptly after the transaction so the NVIDIA kernel module and userspace match.
5. **thermald on Raptor Lake desktops** — optional cheap insurance; the CPU-degradation fix rides microcode, not thermald.

## Standing rejects (do not recommend)

- **Lowering swappiness** on zram-first setups — zram is RAM-speed with ~3x compression; high swappiness (100) is the design, not a misconfiguration.
- **Re-enabling BORE** — upstream disabled it deliberately (EEVDF judged adequate); the modern latency path is a sched_ext scheduler, not a baked-in replacement.
- **Custom kernels (LTO, -O3, self-compiled)** — Nobara already ships the CachyOS optimized build; a custom kernel breaks nobara-sync transactions and the NVIDIA dkms version match.
- **`mitigations=off`** — negligible gain on unaffected CPUs, real security cost.
- **`rcutree.enable_rcu_lazy=1`** — a power-saving trade (CachyOS ships it for handhelds), not a desktop performance win.
- **Growing zram when pinned full** — add/keep a lower-priority disk swapfile instead; growing zram consumes the RAM it exists to protect.
- **THP off / compaction micro-tuning** with ample RAM and MGLRU already enabled — YAGNI.

## Research sources

- Nobara wiki → Modifications → Kernel (current patchset; what is deliberately disabled).
- CachyOS wiki → General system tweaks, sched-ext tutorial, kernel manager (Nobara rides this kernel).
- kernel.org admin guide → intel_pstate (governor/EPP semantics).
- sched_ext ecosystem: upstream scx schedulers repo, OSPM/Kernel Recipes scx_lavd talks, SteamOS scheduling notes.
