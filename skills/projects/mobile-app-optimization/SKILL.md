---
name: mobile-app-optimization
description: Use when fixing mobile app typing lag or APK build.
version: 1.1
author: hermes-agent
license: MIT
---

## When to Use

- Mobile app typing is laggy, unresponsive, or shows "whole sentences before a single letter".
- APK needs to be rebuilt with native plugins (diagnostics, theme, ticker) wired correctly.
- A concurrent session edited a shared file (`chat-landing`) and the fix should be applied to the clean component (`chat-timeline`) instead.
- Real-time measurement is needed (Playwright/browser probe or diagnostics plugin) rather than inference.

# Mobile App Optimization

Always-on rules for mobile performance fixes:

- Measure first with Playwright/browser probes or diagnostics plugin (`stats()`, `dumpLogs()`). Never infer.
- Root cause: check blocking layout (`scrollHeight` sync), timer overhead (`setInterval`), un-memoized re-renders, native thread blocking.
- Conflicts (`<<<<<<<`): resolve before editing; edit clean files (`chat-timeline`) as workaround.
- APK build requires `source .../astra.keystore.env; export KEYSTORE_PASSWORD; ./gradlew assembleRelease`.
- Gate-card UI tweaks follow the owner's standing design orders (check git log comments in GateActivity.kt before redesigning): exactly three choices once/session/deny with `always` filtered at render; Deny sits LEFT of the primary; every severity wears the brand accent (no yellow); the receipt morphs inside the same card, never a second popup; failure restores controls in place with an inline error. When swapping button hierarchy, keep a fallback for gates that lack a choice (e.g. no `session` → `once` becomes primary).
- APK delivery to the phone: copy to `~/uploads/` then Telegram Bot API `sendDocument` with `TELEGRAM_BOT_TOKEN`/`TELEGRAM_HOME_CHANNEL` from `~/.hermes/.env` (Python urllib works from this host; MEDIA: tags only work on gateway surfaces, not TUI).
- Ticker: slow `updateColors()` from 1200ms to 5000ms.
- Reveal timer: slow `useReveal` streaming interval from 16ms to 100ms (`window.setTimeout(tick, done ? 48 : 100)`). This stops the continuous event-loop blocking from frequent state updates.
- After fix: rebuild, retest exact scenario, confirm. "Still laggy" = wrong blocker — the real blocker may be elsewhere (e.g., reveal timer frequency, not just memo + async layout). Confirm with measurement (`scratch/scale-probe.mjs` or `Diagnostics` plugin), never inference.

## Android build + APK facts (proven 2026-10-03; ship-flow proven 2026-10-09 gate-redesign session)

- **JDK pin**: java-25-openjdk on kurama-core is JRE-only (no javac) — gradlew fails with "Toolchain installation does not provide the required capabilities: [JAVA_COMPILER]". Always `JAVA_HOME=/usr/lib/jvm/java-21-openjdk ./gradlew …`.
- **Fresh worktrees can't gradlew**: android/capacitor-cordova-android-plugins/ and android/local.properties are untracked-but-generated — copy both from the primary checkout before any build.
- **Full ship flow** (verified end-to-end 2026-10-09): commit → versionCode/Name bump in android/app/build.gradle → `set -a; source ~/Work/services/astra-android/astra.keystore.env; set +a; JAVA_HOME=java-21 ./gradlew assembleRelease` → verify with `unzip -q apk 'classes*.dex'` + `strings classes.dex | grep '<new literal>'` + output-metadata.json version → `npm run build && systemctl --user restart astra-webui.service` (app loads the live site, so native + web halves must BOTH deploy) → stage APK copy to ~/uploads/ for delivery.
- **Worktree `npm run check` false-fails**: deploy-chunks + doc-preview need `dist/` (run `npm run build` first); sqlite-runtime reads data/astra-training.db which is an empty stub in a worktree — override `ASTRA_DB_PATH=<primary>/data/astra-training.db`. rounding.check bans border-radius 0-3px on ANY selector (not just .ast-cv-* despite the comment) — use 9999px pills for thin accent bars.

- Layer inventory (counted in the session): `NtfyPushService.kt` 822 lines, `GateActivity.kt` 690, `MainActivity.kt` 272, `NativeNtfy.kt` 120, `GateActionReceiver.kt` 76, `BootReceiver.kt` 40, `AstraBarsPlugin.java` 60, `CookieEncryptPlugin.java` 111.
- Version bump proven: `versionCode 30 → 31`, `versionName "1.11.16" → "1.11.17"` via sed on `android/app/build.gradle`.
- JVM unit test: `./gradlew :app:testDebugUnitTest` runs Kotlin test classes under `app/src/test/` (JUnit is already a `testImplementation` dep). Keep the tested code free of `android.*` imports or the JVM tests fail on unmocked Android stubs.
- Plugin verification before claiming: unzip the built APK, `strings classes*.dex | grep -oE '<PluginName>'` — a green `assembleDebug` does not prove a class is inside. Proven working for `AstraThemePlugin` / `AstraThemeRead` / `AstraTokenMath` in v1.11.17.
- Non-obvious API facts proven: `NotificationChannel` has NO colour setter — only `setLightColor` (LED); `NotificationCompat.Builder.setColor` is the accent lever. Action icons (`ic_action_approve/deny`, white vectors) are system-tinted — retheming them is unnecessary. `Color.parseColor` reads `#AARRGGBB`, not CSS `#rrggbbaa`. Android CM contrast on mid-luminance accents: pick text by measured max contrast, not a luminance threshold (Fire `#FF5C1F`: white 3.09:1 vs dark 6.39:1).
- Full theming lesson lives in `projects/astra-webui/SKILL.md` §"Notifications cannot be themed CARDS" — including the platform ceiling (targetSdk 31+ system template) and the two-halves live-fire ship gap (native plugin in APK vs `pushThemeToNative()` only running from the deployed site build).

## Live-fire gate testing (prove the phone leg, not just the server)

To test the approval/gate chain end-to-end without asking the user to tap anything: mint real gates by running gated host commands (`~/.tool-router/route …` trips the shell approval plugin), then read `data/gate-ledger.jsonl` for the verdict. An `answered` row with `"by": "phone"` is PROOF the phone leg worked (notification → popup → answer POST → server forward) — that value is only written by the phone's `/api/gate/:id` path. `"by": "chat"`/`"web"` mean another surface answered it first. Parse the ledger with Python, not grep: entries are one-line JSON with `type: gate|answered` keyed on `id`, and `at` is epoch MILLISECONDS (dividing by 1e3 gives absurd future dates). Pending gates age out of the 30-min TTL harmlessly. Note: a session running with auto-approved gates answers them itself within seconds (`by: chat`) — a pending gate for the phone to answer only survives while the minting session is itself blocked on it.

## Emulator verification loop (the only honest proof for native UI)

A green compile proves nothing about an Activity actually OPENING. The gate popup shipped broken for ~10 days because every APK built clean while the activity crashed in its constructor — invisible until someone tapped it. Any native-UI change (gate popup, notification tap, activity launch) gets the emulator loop BEFORE the APK is handed over:

1. Boot: `ANDROID_AVD_HOME=/home/notjitin/Work/android-sdk/avd ANDROID_SDK_ROOT=$SDK $SDK/emulator/emulator -avd astra36 -no-window -no-audio -gpu swiftshader_indirect -no-snapshot` (background). `emulator -list-avds` shows NOTHING without `ANDROID_AVD_HOME` — an empty list is a wrong-env symptom, not "no AVD exists".
2. Wait: poll `adb shell getprop sys.boot_completed` (~20-60s). adb lives at `/home/notjitin/Work/android-sdk/platform-tools/adb` (not on PATH).
3. Install the release APK, `adb root`, then launch the target with real extras: `am start -n com.jitinnair.astra/.GateActivity --es gate_id <id> --ei notif_id 0` (root bypasses the not-exported SecurityException that blocks a shell start of app-internal activities).
4. Prove state three ways: `dumpsys window | grep mCurrentFocus` (activity holds focus, not bounced to launcher), `logcat -d | grep -E 'AndroidRuntime.*astra|FATAL'` (zero crashes), `uiautomator dump /sdcard/g.xml` + grep `text="…"` (the actual rendered strings — proves the card painted, not just didn't crash).
5. Expired/answered gate IDs are fine for the fetch path (expect "No longer pending"); for full-render proof use GateActivity's `debug_gate_json` string extra, which renders offline with no server.
6. `adb emu kill` when done.
7. For layout changes (button order, widths, positions), assert GEOMETRY from the uiautomator dump — parse each button's `bounds="[x1,y1][x2,y2]"` and check the relationship (above/below, left/right, relative widths), not just that the labels exist. Label presence alone cannot prove a swap.

## Constructor-time Context crash (the class of bug behind a dead popup)

In an Activity, ANY property that touches `AstraThemeRead.tokens(this)` (or any Context-dependent read) must be declared lazy: `private val x get() = …`. An eager `private val x = …` evaluates during `<init>`, BEFORE Android attaches the Context — `getApplicationContext() on a null object reference`, the activity dies in `instantiate()`, and the launcher/notification tap silently no-ops with NO fallback (openChatFallback never runs; the process crashes first). Symptom from the user's seat: "tapping the notification does nothing." Sweep the whole file class after fixing one instance — every colour/theme val in every gate-surface file gets checked, not just the reported line.

A silent crash of this class hides from every build gate: the APK compiles, the class ships, and nothing short of actually launching the activity exposes it. When a native surface "has never been live-verified" (check the project skill/STATUS notes), treat 'it builds' as unproven and run the emulator loop before trusting the surface — a redesign that only polishes the render path leaves a dead launch chain untouched underneath.

References (`references/perf-audit.md`): browser measurement, Playwright patterns, APK verification (`aapt2`), `fitComposer` async (`requestAnimationFrame`), timeline memo.
