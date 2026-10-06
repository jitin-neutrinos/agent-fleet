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
- Ticker: slow `updateColors()` from 1200ms to 5000ms.
- Reveal timer: slow `useReveal` streaming interval from 16ms to 100ms (`window.setTimeout(tick, done ? 48 : 100)`). This stops the continuous event-loop blocking from frequent state updates.
- After fix: rebuild, retest exact scenario, confirm. "Still laggy" = wrong blocker — the real blocker may be elsewhere (e.g., reveal timer frequency, not just memo + async layout). Confirm with measurement (`scratch/scale-probe.mjs` or `Diagnostics` plugin), never inference.

## Android build + APK facts (proven 2026-10-03, theme-aware-notifications session)

- Layer inventory (counted in the session): `NtfyPushService.kt` 822 lines, `GateActivity.kt` 690, `MainActivity.kt` 272, `NativeNtfy.kt` 120, `GateActionReceiver.kt` 76, `BootReceiver.kt` 40, `AstraBarsPlugin.java` 60, `CookieEncryptPlugin.java` 111.
- Version bump proven: `versionCode 30 → 31`, `versionName "1.11.16" → "1.11.17"` via sed on `android/app/build.gradle`.
- JVM unit test: `./gradlew :app:testDebugUnitTest` runs Kotlin test classes under `app/src/test/` (JUnit is already a `testImplementation` dep). Keep the tested code free of `android.*` imports or the JVM tests fail on unmocked Android stubs.
- Plugin verification before claiming: unzip the built APK, `strings classes*.dex | grep -oE '<PluginName>'` — a green `assembleDebug` does not prove a class is inside. Proven working for `AstraThemePlugin` / `AstraThemeRead` / `AstraTokenMath` in v1.11.17.
- Non-obvious API facts proven: `NotificationChannel` has NO colour setter — only `setLightColor` (LED); `NotificationCompat.Builder.setColor` is the accent lever. Action icons (`ic_action_approve/deny`, white vectors) are system-tinted — retheming them is unnecessary. `Color.parseColor` reads `#AARRGGBB`, not CSS `#rrggbbaa`. Android CM contrast on mid-luminance accents: pick text by measured max contrast, not a luminance threshold (Fire `#FF5C1F`: white 3.09:1 vs dark 6.39:1).
- Full theming lesson lives in `projects/astra-webui/SKILL.md` §"Notifications cannot be themed CARDS" — including the platform ceiling (targetSdk 31+ system template) and the two-halves live-fire ship gap (native plugin in APK vs `pushThemeToNative()` only running from the deployed site build).

References (`references/perf-audit.md`): browser measurement, Playwright patterns, APK verification (`aapt2`), `fitComposer` async (`requestAnimationFrame`), timeline memo.
