---
name: multiboot-external-drives
description: Use when installing OSes to external drives or multibooting.
---

# Multiboot & External-Drive OS Installs on kurama-core

## Verified host boot facts (checked live 2026-09-06)

- Board: MSI Z790 (MS-7E06, PRO Z790-P WiFi family). Boot menu key: **F11**; external drives appear as `UEFI: <drive name>`.
- Boot mode: UEFI only in practice. **Secure Boot disabled** (Nobara kernel requires it off; Kali and CachyOS also want it off — no conflict).
- Host GRUB 2.12, shim at `\EFI\fedora\shimx64.efi` on the internal ESP (nvme0n1p1). Internal ESP also hosts Windows Boot Manager and a stale `ubuntu` NVRAM entry (harmless residue).
- Internal disks: nvme0n1 = Windows (p3/p4 NTFS) + Nobara (ESP p1, ext4 /boot p5, btrfs p6); nvme1n1 = ext4 game drive; sda = 2TB NTFS data (dual-boot — never touch).
- USB: Intel 700-series xHCI, 20 Gbps port available. See `references/research-2026-09.md` for chipset guidance (Realtek RTL9210B good; JMicron JMS583 has documented Linux hangs).

## The plan (agreed with user 2026-09-06)

1. Internal Nobara + Windows dual-boot stays until user says otherwise. Windows move to external is DEFERRED — user's external is a WD 2.5" spinning HDD; Windows To Go on a spinning disk is the weakest link (discontinued feature, Rufus workaround, poor random I/O). Recommend NVMe-in-enclosure before moving Windows.
2. Install Kali Linux on the external 1TB HDD (full install, not live-with-persistence). CachyOS also planned.
3. Boot flow: F11 at power-on → external drive entry → distro's own menu. Internal BootOrder untouched.

## Windows-side repair (internal dual-boot)

When the Windows half of the internal dual-boot breaks (black screen, no display, remote
lockout), it can be diagnosed and repaired from Nobara without ever booting Windows:
read-only mount the NTFS partition, parse the registry hives offline (regipy), read event
logs (python-evtx), and edit hives with reged/chntpw. Proven workflow, key registry paths,
and the VDD-strands-host failure class live in
`references/windows-dual-boot-forensics.md`.

## Install procedure (per distro, onto external drive)

1. Back up the external disk first — repartitioning erases it.
2. GPT layout on external: p1 1GB FAT32 ESP (shared), then one root per distro (ext4 for Kali, btrfs for CachyOS), remainder exFAT/NTFS shared data.
3. Boot the installer ISO (F11), manual partitioning, target ONLY the external disk.
4. **Bootloader must go to the EXTERNAL ESP** — in CachyOS Calamares the "Install boot loader on:" field must point at the external disk, never `/dev/nvme0n1`. This is the single most common failure: an installer grabbing the internal ESP breaks the host dual-boot when the drive is unplugged.
5. Use GRUB `--removable` when installing by hand so it writes the universal fallback `\EFI\BOOT\BOOTX64.EFI` (no NVRAM dependency — this is what makes the drive portable). GNU GRUB manual confirms the flag.
6. fstab and grub.cfg must reference UUIDs, never `/dev/sdX`.
7. Initramfs must be generic (dracut/mkinitcpio non-hostonly) if the drive should boot on other machines. Ubuntu/Fedora-family defaults are already generic.
8. Optional but bulletproof: physically unplug both internal NVMe drives during install, reinstall them after. Zero risk to Windows/Nobara.
9. After install: NVIDIA proprietary driver per distro (Kali: `nvidia-driver` from non-free; CachyOS: offered at install time).

## Distro-specific notes

- **Nobara**: needs 3 partitions (ext4 /boot + FAT32 /boot/efi + root); cannot nest /boot in btrfs root. Kernel refuses Secure Boot.
- **CachyOS**: offers systemd-boot / rEFInd / GRUB / Limine in Calamares. CachyOS wiki warns some MSI boards have UEFI quirks with GRUB/rEFInd — fallback is systemd-boot or Limine. Host GRUB already proven working on this board, so GRUB is fine; switch to Limine if the installer's GRUB misbehaves.
- **Kali**: official docs cover full standalone install on USB drives, including LUKS-encrypted variant.

## Performance reality check

OS on spinning USB HDD works but random 4K I/O is the bottleneck for daily use; tolerable for Kali's CLI workload. SATA SSD in enclosure ≈ 400–500 MB/s seq / 30–50 MB/s 4K — feels normal. NVMe enclosure ≈ USB-bus speed. Cite numbers from `references/research-2026-09.md`.

Full citations (Kali docs, CachyOS wiki, Rufus/WTG guides, enclosure chipset threads, AI-distro landscape, mac-like distro rankings) live in `references/research-2026-09.md`.