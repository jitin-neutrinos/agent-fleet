---
name: steam-proton-apps
description: Use when stopping, relaunching, or debugging Steam apps.
risk: safe
---

# Steam / Proton-wrapped app control

## Fully stopping a Proton-wrapped Steam app (e.g. Wallpaper Engine)

1. Enumerate first: `pgrep -af -i "<appname>"` plus `pgrep -af iscriptevaluator`. Windows processes show their `S:\steamapps\...` cmdline but are real host PIDs.
2. Kill the WHOLE chain in one pass: app processes AND their Steam wrapper ancestors. The parent chain is usually `srt-bwrap -> pv-adverb -> .../proton run ~/.local/share/Steam/legacycompat/iscriptevaluator.exe`. Walk up with `ps -o pid,ppid,cmd -p <pid>` and kill from the top.
3. Verify AFTER a wait (15s): `pgrep -af -i "<appname>" | grep -v hermes`. Steam's legacycompat wrapper auto-RESPAWNS the app's service process — killing only the app processes (or only the wrapper) just re-seeds new PIDs; re-check until a clean pass stays clear.
4. Report that the app's UI window may pop open when its service is killed mid-run (Wallpaper Engine opens its browser window); close it in the same sweep with `pkill -9 -f -i <appname>`.

## Pitfalls

- NEVER `pkill -9 -f <short-pattern>` for these: the pattern matches your OWN terminal wrapper's command line (the shell command text contains the pattern) and SIGKILLs your own session mid-call. Either enumerate PIDs first and kill by PID, or use a pattern that cannot appear in your own command line and exclude self.
- Killing only leaf processes fails silently — the respawn parent is Steam's legacycompat evaluator, not the app. Trace PPID to the top before killing.
- Check `systemctl --user list-unit-files | grep -i <appname>` for user units that may relaunch on login, and `~/.config/autostart/`, before declaring the app fully stopped.

## Relaunch

User relaunches Wallpaper Engine (and other Steam apps) from Steam themselves — do not launch it for them unless asked.
