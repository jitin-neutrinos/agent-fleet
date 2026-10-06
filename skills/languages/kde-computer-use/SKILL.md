---
name: kde-computer-use
description: Inspect and control a KDE Plasma desktop from Codex using KWin DBus, kdotool, Spectacle, kscreen-doctor, and related local tools. Use when the user asks Codex to interact with the current desktop, inspect windows, switch desktops, move/resize/activate/close windows, trigger KDE shortcuts or KWin effects, take screenshots, query monitors, or troubleshoot computer-use automation on KDE/Wayland or KDE/X11.
---

# KDE Computer Use

## Overview

Use KDE-native automation first: KWin DBus and `kdotool` for window/desktop actions, Spectacle for captures, `kscreen-doctor` for monitor state, and `ydotool` only when semantic APIs cannot do the job.

Before acting from a TTY, non-graphical shell, or background agent, reconstruct the active KDE session environment and inspect the live desktop:

```bash
/path/to/kde-computer-use/scripts/kde-inspect-session
```

Load the session environment for one command or for a shell:

```bash
/path/to/kde-computer-use/scripts/kde-session-env -- kdotool getactivewindow getwindowname
source /path/to/kde-computer-use/scripts/kde-session-env
```

Use the bundled scripts for repeated multi-command operations:

```bash
/path/to/kde-computer-use/scripts/kde-window-info --active
/path/to/kde-computer-use/scripts/kde-window-info --title 'Firefox|Konsole'
/path/to/kde-computer-use/scripts/kde-focus-window --title 'kitty' --click
/path/to/kde-computer-use/scripts/kde-type-text --enter 'btop'
/path/to/kde-computer-use/scripts/kde-screenshot --active --output /tmp/active.png
```

## Workflow

1. Confirm the session with `loginctl show-user "$USER" -p Display -p State -p Sessions` and `loginctl show-session <id> -p Type -p Desktop -p Active -p State`.
2. Load the KDE environment if `DISPLAY`, `WAYLAND_DISPLAY`, or `DBUS_SESSION_BUS_ADDRESS` is missing.
3. Inspect before acting: active window, relevant windows, mouse position, desktop, active output, and monitor geometry.
4. Prefer semantic window and desktop operations over raw input. Use `kdotool`, KWin DBus, or global shortcuts before `ydotool`.
5. Use screenshots to verify visible state after actions when the task depends on UI layout.
6. Avoid interactive DBus methods such as `queryWindowInfo` unless the user expects a click/pick operation.
7. For disruptive actions such as closing windows, sending keystrokes, moving displays, or changing DPMS, inspect first and state the exact action before doing it unless the user explicitly requested that action.

## Launching Applications

Launch GUI programs through `kde-session-env --`, detach anything that should become a visible independent window, then verify by window query and screenshot. A successful shell exit or a new process is not enough proof that KWin mapped a usable window.

For shell builtins, aliases, or compound checks, wrap the command in a shell:

```bash
/path/to/kde-computer-use/scripts/kde-session-env -- sh -lc 'command -v kitty; command -v qdbus6'
```

For kitty, prefer `--detach` and a distinctive title when opening a fresh terminal from Codex:

```bash
/path/to/kde-computer-use/scripts/kde-session-env -- kitty --detach --title Codex-fastfetch sh -lc 'fastfetch; exec "${SHELL:-zsh}"'
sleep 1
/path/to/kde-computer-use/scripts/kde-window-info --title '^Codex-fastfetch$'
/path/to/kde-computer-use/scripts/kde-screenshot --fullscreen --output /tmp/desktop.png
```

## Failure Handling

- If `qdbus6` cannot connect, run `scripts/kde-session-env` and confirm `/run/user/$(id -u)/bus` exists.
- If a program launch appears to succeed but no window appears, retry with app-specific detach flags or `sh -lc 'setsid -f app ...'`, then verify with `kde-window-info` and a screenshot.
- If `kde-session-env -- command -v ...` fails, remember `command` is a shell builtin; use `kde-session-env -- sh -lc 'command -v ...'`.
- If a window is KWin-active but does not receive text, focus with `kde-focus-window --click` before `kde-type-text`.
- If `ydotool` fails, check `systemctl --user status ydotool.service --no-pager` and fall back to KWin, `kdotool`, or global shortcuts.
- If screenshots fail under Wayland, prefer Spectacle; do not default to wlroots-only tools such as `grim` on Plasma.
- If display configuration is involved, capture `kscreen-doctor -o` before and after the change.

## Common Commands

Use `KDE_ENV=/path/to/kde-computer-use/scripts/kde-session-env` in examples below.

```bash
$KDE_ENV -- /path/to/kde-computer-use/scripts/kde-inspect-session
$KDE_ENV -- qdbus6 org.kde.KWin /KWin
$KDE_ENV -- qdbus6 org.kde.KWin /KWin org.kde.KWin.currentDesktop
$KDE_ENV -- qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName
$KDE_ENV -- kdotool getactivewindow getwindowname getwindowgeometry getwindowclassname
$KDE_ENV -- kdotool search --title 'Firefox|Konsole' getwindowid getwindowname
$KDE_ENV -- kdotool search --title 'Konsole' windowactivate
$KDE_ENV -- kdotool getmouselocation --shell
$KDE_ENV -- kscreen-doctor -o
$KDE_ENV -- spectacle --background --nonotify --fullscreen --output /tmp/desktop.png
```

Read `references/kde-api-notes.md` for method names, gotchas, and tool selection guidance.

## Safety

Window closing, global shortcuts, pointer/keyboard injection, and display reconfiguration affect the user's live desktop. Inspect state first, make the smallest action that satisfies the request, and report irreversible or disruptive actions before doing them unless the user explicitly asked for them.
