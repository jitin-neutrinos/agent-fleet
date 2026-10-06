# Research: external-drive multiboot, AI distros, mac-like distros (2026-09-06)

Condensed citations gathered while planning Kali/CachyOS/Windows-on-external for kurama-core.

## Booting & installing to external drives

- GNU GRUB manual — `grub-install --efi-directory=<esp> --boot-directory=<dir> --removable` writes the portable fallback loader: https://www.gnu.org/software/grub/manual/grub/
- Kali official — full standalone (non-live) install on USB drive, incl. fully LUKS-encrypted variant: https://kali.org/docs/usb/usb-standalone-encrypted
- ArchWiki — removable-medium installs; generic initramfs requirement (block/keyboard hooks before autodetect); hybrid BIOS+UEFI layout: https://wiki.archlinux.org/title/Install_Arch_Linux_on_a_removable_medium
- ArchWiki — multiboot USB drive (GRUB loopback ISOs, automated tools GLIM, liveusb-builder): https://wiki.archlinux.org/title/Multiboot_USB_drive
- AskUbuntu — why portable external installs break across machines (NVRAM-bound bootloader) and the EFI/BOOT fallback fix: https://askubuntu.com/questions/503796/
- AskUbuntu — installer grabbing internal ESP breaks host boot when drive unplugged: https://askubuntu.com/questions/647479/
- Portable full-install script with removable UEFI bootloader, no NVRAM writes: https://github.com/lobo235/ubuntu-external-install
- Guide — portable external NVMe install, removable GRUB, UUID discipline, MSI F11: https://kamrulhassan7740.medium.com/installing-portable-linux-on-external-nvme-uefi-only-grub-safe-no-host-interference-79919e003aff

## CachyOS specifics

- Installation guide (manual partitioning, "Install boot loader on:" must point at target disk): https://wiki.cachyos.org/installation/installation_on_root/
- Boot managers compared (systemd-boot / rEFInd / GRUB / Limine); **MSI boards: some have non-compliant UEFI causing GRUB/rEFInd issues — systemd-boot or Limine are the reliable fallbacks**: https://wiki.cachyos.org/installation/boot_managers/
- Boot manager config (sdboot-manage, grub-mkconfig, grub-btrfs-support): https://wiki.cachyos.org/configuration/boot_manager_configuration/
- NVIDIA driver open↔proprietary switching: https://discuss.cachyos.org/t/how-to-change-nvidia-drivers-from-open-to-proprietary/6402

## Windows on external (deferred)

- Windows To Go discontinued; Rufus "Windows To Go" image option is the workaround; USB SSD strongly recommended; use "Prevent Windows To Go from accessing the internal disks": https://pureinfotech.com/create-windows-to-go-rufus-windows-11-usb/

## Storage performance

- USB flash vs external SSD vs internal (4K random I/O is what matters for OS use; flash drives die in months under OS write loads): https://selfhosting.sh/hardware/usb-boot-home-server/
- Enclosure chipsets: JMicron JMS583 documented Linux mount hangs/UAS errors; Realtek RTL9210B reliable: https://forum.endeavouros.com/t/slow-mounting-of-nvme-ssd-in-usb-enclosure/67555/1
- HDD vs SSD vs NVMe-over-USB speed classes: https://forum.garudalinux.org/t/garuda-users-opinions-on-their-favorite-external-hard-drive-storage/41650/8

## AI-integrated distros (researched for user's interest)

- Deepin 25 — UOS AI built in, local execution, DeepSeek-R1 integration: https://www.deepin.org/en/deepin-25-uos-ai/ and https://www.deepin.org/en/uos-ai-integration-with-deepseek-r1/
- Deepin 25.1 independent coverage (multi-model switching, local AI): https://linuxlap.com/linux-distributions-distros-news/deepin-ai-integrated-linux-distro/
- MakuluLinux LinDoz 2025 / Max — Electra AI (text/image/audio/video, voice avatar); runs on vendor servers, NOT local; one-developer project: https://www.linuxinsider.com/story/makululinux-lindoz-2025-brings-ai-frontier-to-desktop-computing-177504.html
- aiOS (experimental, Ubuntu 24.04 + llama.cpp daemon, hobby grade): https://github.com/thoerner/ai-os
- AVOID Gnoppix "AI Linux" — local-AI claims false (online-only tool), broken packages: https://zdnet.com/article/i-tried-a-linux-distro-that-promises-free-built-in-ai-and-things-got-weird and http://news.tuxmachines.org/n/2025/12/01/Review_Gnoppix_AI_Linux_25_10.shtml
- Distro matters less than GPU drivers for real AI work; RTX 4070 Ti SUPER 16GB + 62GB RAM is a strong local-inference box via Ollama+CUDA on any mainstream distro: https://www.opensourcefeed.org/best-linux-distro-local-llm/

## Mac-like / premium aesthetic distros

- elementary OS 8 — consensus closest "feels like macOS" daily driver: https://unstore.io/discover/best-apps-for-mac-like-linux-distros-desktop
- Deepin 25 — most visually striking (also the top AI-integrated pick; intersection of both requests): https://xda-developers.com/linux-distros-that-look-better-than-windows-11-and-macos
- Zorin OS — Mac layout built in, Ubuntu LTS base, Pro pack $49: https://tech.yahoo.com/computing/articles/5-most-beautiful-linux-distros-150016419.html
- Roundup incl. Garuda (neon cyberpunk KDE, gaming), BigLinux, Pop!_OS: https://techlife.blog/posts/beautiful-linux-distros-2024
- Small Mac-clone projects (Pear OS, Ling Mo, cutefish-based) = single-maintainer, treat as toys.

## Nobara facts

- Requires UEFI, Secure Boot disabled, 3 partitions (/boot ext4 + /boot/efi FAT32 + root); recommends Ventoy for media: https://wiki.nobaraproject.org/en/new-user-guide-general-guidelines
- Background: https://en.wikipedia.org/wiki/Nobara_(operating_system)