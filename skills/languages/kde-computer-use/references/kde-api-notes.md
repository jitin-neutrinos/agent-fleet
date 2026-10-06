# KDE API Notes

## Session Environment

Commands launched by Codex may run outside the graphical session. If DBus or window tools cannot connect, load:

```bash
source /path/to/kde-computer-use/scripts/kde-session-env
```

For a complete preflight report, run:

```bash
scripts/kde-inspect-session
```

Equivalent essentials on this desktop are:

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
export WAYLAND_DISPLAY=wayland-0
export DISPLAY=:0
```

Confirm session facts:

```bash
loginctl list-sessions --no-legend
loginctl show-session <id> -p Type -p Desktop -p Active -p State -p TTY
busctl --user list
```

Common failures:

- `Cannot autolaunch D-Bus without X11 $DISPLAY`: load `DBUS_SESSION_BUS_ADDRESS` from `kde-session-env`.
- `Could not connect to display`: load `WAYLAND_DISPLAY` and `DISPLAY`, then retry through `kde-session-env --`.
- Tools work in an interactive terminal but not from Codex: use the helper wrapper for every command in the sequence.
- `kde-session-env -- command -v foo` fails: `command` is a shell builtin, not an executable. Use `kde-session-env -- sh -lc 'command -v foo'`.

## Launching GUI Programs

When a user asks to open an application, launch it inside the KDE session and verify that KWin mapped the expected window. Do not treat a zero exit status, launcher return, or `pgrep` result as proof that the visible desktop changed.

General pattern:

```bash
scripts/kde-session-env -- sh -lc 'setsid -f app --args >/tmp/app-launch.log 2>&1'
sleep 1
scripts/kde-window-info --title 'distinctive-title|expected-window-title'
scripts/kde-screenshot --fullscreen --output /tmp/desktop.png
```

For kitty specifically, use `--detach` and a unique title. Launching kitty without detaching from a background Codex command can appear to succeed while leaving no separately discoverable window, and broad class searches can return only an existing kitty window.

```bash
scripts/kde-session-env -- kitty --detach --title Codex-fastfetch sh -lc 'fastfetch; exec "${SHELL:-zsh}"'
sleep 1
scripts/kde-window-info --title '^Codex-fastfetch$'
scripts/kde-screenshot --fullscreen --output /tmp/desktop.png
```

If the title search fails, inspect all likely windows before acting on the active one:

```bash
scripts/kde-session-env -- kdotool search --class 'kitty|konsole|org.kde.konsole' getwindowid getwindowname getwindowpid getwindowgeometry
scripts/kde-session-env -- kdotool getactivewindow getwindowname getwindowclassname getwindowpid getwindowgeometry
```

Launchers such as `gtk-launch kitty.desktop` may return successfully without creating a new window if the desktop entry or application reuses an existing instance. Prefer direct application commands with explicit detach and title options when a fresh window matters.

## KWin DBus

Introspect before relying on a method:

```bash
qdbus6 org.kde.KWin /KWin
qdbus6 org.kde.KWin.ScreenShot2 /org/kde/KWin/ScreenShot2
qdbus6 org.kde.kglobalaccel /component/kwin
```

Useful KWin methods:

```bash
qdbus6 org.kde.KWin /KWin org.kde.KWin.currentDesktop
qdbus6 org.kde.KWin /KWin org.kde.KWin.setCurrentDesktop 2
qdbus6 org.kde.KWin /KWin org.kde.KWin.nextDesktop
qdbus6 org.kde.KWin /KWin org.kde.KWin.previousDesktop
qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName
qdbus6 org.kde.KWin /KWin org.kde.KWin.showDesktop true
qdbus6 org.kde.KWin /KWin org.kde.KWin.showDesktop false
qdbus6 org.kde.KWin /KWin org.kde.KWin.getWindowInfo '{window-uuid}'
```

`queryWindowInfo` is interactive and waits for the user/agent to click a window. Avoid it during unattended work.

Trigger KWin global shortcuts through kglobalaccel:

```bash
qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.shortcutNames
qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut 'Overview'
qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut 'Window Quick Tile Left'
```

## kdotool

`kdotool` is the preferred xdotool-like layer for KDE 5/6, including Wayland.

```bash
kdotool getactivewindow
kdotool getactivewindow getwindowname getwindowgeometry getwindowclassname getwindowpid
kdotool search --title 'pattern' getwindowid getwindowname
kdotool search --class 'konsole' windowactivate
kdotool search --title 'pattern' windowsize 1200 800 windowmove 50 50
kdotool getmouselocation --shell
kdotool get_desktop
kdotool set_desktop 1
scripts/kde-window-info --title 'Firefox|Konsole'
```

Window selectors:

- `%1`, `%2`, etc. select from the previous query stack.
- `%@` selects all windows in the query stack.
- `{uuid}` selects a concrete KWin window id.

Prefer `windowactivate`, `windowmove`, `windowsize`, `windowminimize`, `windowstate`, and desktop commands over pointer injection.

When you need every matching window id, use `%@`:

```bash
kdotool search --title '.+' --limit 20 getwindowid %@
```

Search patterns are regular expressions. A narrow pattern is safer than `.*`, because untitled panels and shell surfaces may match broad class searches.

## Screenshots

On this KDE Wayland desktop, `spectacle` works for background screenshots:

```bash
scripts/kde-screenshot --active --output /tmp/window.png
scripts/kde-screenshot --fullscreen --output /tmp/desktop.png
scripts/kde-screenshot --active --pointer --delay 250 --output /tmp/window.png
spectacle --background --nonotify --fullscreen --output /tmp/desktop.png
spectacle --background --nonotify --current --output /tmp/current-monitor.png
spectacle --background --nonotify --activewindow --output /tmp/window.png
```

`grim` may fail under KWin with `compositor doesn't support the screen capture protocol`; it is primarily a wlroots tool and should not be the first choice on Plasma.

KWin exposes `org.kde.KWin.ScreenShot2`, but its methods require a DBus Unix file descriptor pipe. Use Spectacle unless direct pipe handling is worth the extra code.

## Monitors

Inspect display configuration:

```bash
kscreen-doctor -o
qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName
```

Use `kscreen-doctor` for deliberate monitor reconfiguration only after inspecting current outputs. Reconfiguration is live and can disrupt the user's desktop.

For changes, prefer one atomic `kscreen-doctor` invocation containing all output settings. Inspect first, state the intended target, then verify with `kscreen-doctor -o`.

## Synthetic Input

Use `ydotool` only when a semantic API cannot do the job. It needs `ydotoold`:

```bash
scripts/kde-focus-window --title 'target title' --click
scripts/kde-type-text --enter 'text'
printf '%s\n' 'multi line text' | scripts/kde-type-text --stdin
systemctl --user status ydotool.service --no-pager
systemctl --user start ydotool.service
ydotool mousemove --absolute -- 100 100
ydotool click 0xC0
ydotool type -d 100 -H 50 'text'
ydotool key -d 100 28:1 28:0
```

On KDE Wayland, first activate the window with KWin or `kdotool`, then click inside the target surface before typing. A window can be KWin-active while the terminal/application widget still does not receive injected text.

If the daemon is inactive or permissions fail, report that synthetic input is unavailable and fall back to KWin/kdotool APIs where possible.

## Action Recipes

Focus an application and verify:

```bash
scripts/kde-window-info --title 'Konsole|kitty'
scripts/kde-focus-window --title 'Konsole|kitty'
scripts/kde-screenshot --active --output /tmp/focused.png
```

Send text only after a click into the surface:

```bash
scripts/kde-focus-window --title 'Konsole|kitty' --click
scripts/kde-type-text --enter 'uptime'
```

Move a window without raw mouse input:

```bash
scripts/kde-window-info --active
kdotool getactivewindow windowsize 1200 800 windowmove 40 40
```

Trigger a KWin shortcut without injecting key presses:

```bash
qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut 'Overview'
```

## Tool Selection

Use this order:

1. KWin DBus for desktop state, KWin effects, global shortcuts, and exact KWin methods.
2. `kdotool` for finding and manipulating windows.
3. Spectacle for screenshots.
4. `kscreen-doctor` for monitor state and carefully chosen output changes.
5. `ydotool` for last-resort keyboard/mouse injection.
