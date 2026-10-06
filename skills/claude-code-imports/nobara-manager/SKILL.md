---
name: nobara-manager
description: >-
  Use this skill to manage Nobara Linux configurations, themes, package installations, and system maintenance.
---

# Nobara Linux Manager

Use this skill to safely administer Nobara Linux.

## Guidelines
1. **Package Management**: Always use `sudo dnf` instead of `apt` or `pacman`. Avoid overriding Nobara's custom COPR repos.
2. **System Updates**: Nobara has a specific update tool (`nobara-sync`). Prefer running system updates through Nobara's approved methods.
3. **Themes and Colors**: Respect the default Nobara theming. When changing themes via GNOME/KDE settings, ensure compatibility with Nobara's pre-installed extensions.
4. **Gaming & Drivers**: Nobara comes pre-configured with drivers and gaming tools (Proton, Wine). Do not attempt to reinstall these manually unless specifically requested.
