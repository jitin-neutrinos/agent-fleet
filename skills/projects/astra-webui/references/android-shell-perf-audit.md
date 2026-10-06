# Android shell — speed / memory / storage / queue audit

Read-only forensic pass over the Capacitor Android shell (`android/`) plus the web surface it
loads (`src/`) and the proxy (`server/`). Produces a findings report; changes nothing.

Applies to any Capacitor app whose WebView points at a live URL — the shape where most cost
lives OUTSIDE the native layer.

## Order of work

1. **Map the stack before judging it.** Read every native source file (they are small —
   the whole Astra layer is ~2k lines). Find the WebView's content source in
   `capacitor.config.ts` (`server.url` vs `webDir`); that single key decides whether the
   bundled web assets are live or dead.
2. **Artifact forensics** (below) — cheap, decisive, and immune to stale comments.
3. **Timer/render audit** on the JS layer.
4. **Storage + queue inventory** on the JS layer.
5. **Research** vendor docs for anything you'd otherwise guess at (FGS types, WebView memory,
   R8). Cite, don't assert from memory.
6. **Write the report, change nothing.** Prioritized table (P0/P1/P2 + effort + risk), an
   explicit "could not verify" section, and a measurement plan.

## Artifact forensics

```bash
cd android/app/build/outputs/apk/debug        # or release
unzip -l app-debug.apk | awk '/classes.*\.dex/{s+=$1} END{print "dex",s}'
unzip -l app-debug.apk | awk '/classes.*\.dex/' | wc -l      # ≥4 ⇒ R8 is OFF
unzip -l app-debug.apk | awk '/assets\/public\//{s+=$1} END{print "bundled web",s}'
unzip -l app-debug.apk | awk '/  res\//{s+=$1} END{print "res",s}'
```

- **dex file count is the R8 tell.** 8 files for ~2k lines of your own Kotlin means
  `minifyEnabled false`. Check the base file too — `proguard-android.txt` is NOT
  `proguard-android-optimize.txt`, and Google's R8 docs require the latter for full
  utilization. Expect >50% size reduction from `minifyEnabled + shrinkResources` together.
  **Risk:** Capacitor resolves plugins reflectively (`@CapacitorPlugin` / `@PluginMethod`) —
  minified builds need keep rules and a real-device smoke test. Do not ship this blind.
- **`assets/public/` under a `server.url` app is dead weight.** The WebView loads the
  network copy and never reads the bundle. Confirm with mtimes:
  `stat -c '%y' android/app/src/main/assets/public/index.html dist/index.html` — a bundled
  `index.html` older than the last `dist/` build is a fossil, and it doubles as a latent trap
  for anyone who flips `server.url` off for a real bundled build.

## Bundle forensics (web layer)

```bash
cd dist/assets
for f in index-*.js index-*.css; do
  echo "$f raw=$(stat -c%s $f) gz=$(gzip -c $f|wc -c) br=$(brotli -c $f 2>/dev/null|wc -c)"
done
# which libraries actually landed in the always-loaded main chunk
for lib in <suspicious deps>; do echo "$lib: $(grep -c "$lib" index-*.js)"; done
```

- Report **gzipped** size as the real transfer cost and raw as the parse cost — they point
  at different fixes.
- Grep the SERVED main chunk for library signature strings, not the source imports (the
  lazy-boundary pitfall in SKILL.md applies).
- **Dead dependency check:** a prod dependency with zero importers anywhere in `src/` is an
  install-time and supply-chain cost only — it is tree-shaken out of the bundle. Report it
  as build hygiene, never as a bundle win. Grep for importers, don't infer from the dep list.
- **Render-blocking third-party CSS** in `index.html` (Google Fonts `<link rel=stylesheet>`)
  is the most concrete cold-start win: the browser cannot paint until it lands. Self-host
  subset woff2 with `font-display: swap`.

## Timer / render audit

```bash
grep -rn 'setInterval(' src --include=*.ts --include=*.tsx | grep -v '\.check\.' | wc -l
grep -rc 'memo(' src/components/*.tsx | grep -v ':0'    # 0 hits ⇒ nothing memoized
```

- **An unconditional interval calling a store `set()` is only expensive when the written
  VALUE actually changes.** A selector subscription bails out on `Object.is` equality, so
  `setState({nextRetryIn: 0})` 3600×/hour re-renders nobody — the "forever" claim is wrong.
  The real cost is scoped to when the value differs each tick (a live countdown during an
  outage), plus its blast radius: a subscription at the TOP of the tree feeds a leaf label.
  **Fix by moving the subscription down to the component that renders the value**, not by
  guarding the timer.
- **Prove the re-render claim with a minimal repro before you write it in a report.** A
  selector-equality test is a dozen lines and needs no DOM — subscribe via the vanilla store,
  `setState` N times, count selector-equal transitions. Assert the number, not the mechanism:
  an audit that reports "permanent 1 Hz re-render of the whole chat" without that test is
  asserting something the framework already prevents, and shipping a fix on the strength of
  it is how you spend a P0 on a non-problem. See `check-suite-and-ci.md` §3 for the same
  discipline applied to "it only fails in parallel".
- **Self-resetting polls:** a `useEffect` whose dep array includes the state its own poll
  callback writes tears down and re-arms its own interval on every reconciliation.
- Streaming render paths that `marked.parse` + `DOMPurify.sanitize` inside a `useMemo` keyed
  on the growing text re-parse the WHOLE reply per token — O(n²) over a long answer. Fix is
  block-level memoization (`marked.lexer` → one memoized component per block, only the last
  block changes while streaming).
- 1 Hz tickers that exist only to advance a clock label should render the time from a ref or
  a direct DOM write, not through a state write.

## Storage + queue inventory

Build a table of EVERY key the app writes, with its cap/TTL/prune path:

```bash
grep -rhoE '"astra[-a-z_0-9:]*"|`astra[-a-z_0-9:${}.]*`' src --include=*.ts --include=*.tsx \
  | grep -v check | sort -u
```

Then diff the write sites against the prune sweep's prefix list. **A sweep that covers one
key prefix leaves its siblings growing forever** — sibling keys written by the same feature
are the usual miss. Everything `try/catch`-wrapped against quota fails *silent*, so
storage exhaustion shows up as dock state quietly not persisting, not as an error.

Queue review checks: is there exactly ONE durable queue per concern (two is a trap for the
next editor — verify with importer greps); does the cap live in both the load AND the save
path; is the stale-item drop covered by a check file.

## Report shape the owner expects

- KPI canvas at the top, then a findings table with a **confidence column**.
- Anything not measured on a device says so inline. When `adb devices` is empty, every
  speed/memory number is derived from source, artifacts, and vendor docs — **never present an
  estimate as a measurement**. Give a measurement plan instead.
- Close with a prioritized table (P0/P1/P2 + effort + risk) and a short "deliberately not
  recommended" list, so a future session doesn't re-litigate settled decisions.
- Write to a NEW file under `docs/research/` and touch nothing else — in a shared repo,
  `git status` shows other sessions' dirty files; they are not yours.

## Turning a finding on (implementation notes)

### R8: the keep rules ARE the feature, so prove them at the dex level

The empty `proguard-rules.pro` is why R8 was never safe to enable — turning it on without them
silently empties Capacitor's reflectively-built plugin map, and the web layer swallows those call
failures by design, so push just quietly stops working. Keep rules needed: `@CapacitorPlugin`
classes, `@PluginMethod` members **and their names** (the JS-facing contract), the Cordova layer,
`@PermissionCallback`, OkHttp/Conscrypt/BouncyCastle `-dontwarn`, Tink.

- **`-keep @SomeAnnotation <members>;` at top level is a ProGuard PARSE ERROR, not a silent
  no-op** — R8 fails the build. Annotation-on-members must be
  `-keepclassmembers class * { @SomeAnnotation <methods>; }`. Budget a build cycle for this.
- **"It compiles" does not prove the plugin map survived.** Grep the built dex directly:
  ```bash
  unzip -o -q app/build/outputs/apk/release/app-release.apk 'classes*.dex' -d /tmp/dexchk
  DD=$(ls -t ~/Work/android-sdk/build-tools/*/dexdump | head -1)
  for d in /tmp/dexchk/classes*.dex; do $DD -f "$d" | grep -oE 'Lcom/<pkg>/[A-Za-z$]+;'; done | sort -u
  for d in /tmp/dexchk/classes*.dex; do $DD -d "$d" | grep -A2 PluginName | grep -oE "'[a-zA-Z]+'"; done | sort -u
  ```
  Assert your own classes survive **unrenamed** and every `@PluginMethod` name is still a literal
  string in the dex. That, not a successful build, is the smoke test this change needs.
- Kotlin gotcha in a file that mixes Java-style and Kotlin declarations: `public class X : Y()` is
  Kotlin, so `private static final String` does not compile in it — use a `companion object` with
  `private const val`.

### Excluding dead assets: expect the two obvious approaches to fail

`assets/public/**` under a `server.url` app must not ship. Both obvious fixes silently do nothing
or break the build, so budget for iteration and **always verify against the built archive**, never
the build log — a green build with the files still present looks identical to a fix:

| Approach | Result |
|---|---|
| `aaptOptions.ignoreAssetsPattern` with `public/*` | Rebuilt APK still contains every file |
| `delete` from the merged-assets intermediate | Merge task recreates it; APK unchanged |
| `dependsOn` from the merge task | Gradle: circular dependency |
| `finalizedBy` on the packaging task | Runs AFTER the archive is written; APK unchanged |

What works: **move the source directory aside before packaging, restore it after**, hooked with
`dependsOn` on `package*` plus `finalizedBy` on the restore task — so a failed build still leaves
`npx cap copy android` and any future bundled build working.

```groovy
def bundledWebDir = file('src/main/assets/public')
def bundledWebStash = file("${project.buildDir}/bundled-web-stash")
tasks.register('stripBundledWebAssets')  { doLast { if (bundledWebDir.exists()) { bundledWebDir.renameTo(bundledWebStash) } } }
tasks.register('restoreBundledWebAssets') { doLast { if (bundledWebStash.exists())  { bundledWebStash.renameTo(bundledWebDir) } } }
tasks.matching { it.name.startsWith('package') }.configureEach {
    dependsOn 'stripBundledWebAssets'; finalizedBy 'restoreBundledWebAssets'
}
```

An unchanged APK mtime after a "successful" rebuild means Gradle skipped packaging — clear
`app/build/outputs/apk` and confirm the timestamp moved before believing any measurement.

### Self-hosting fonts: assert the font is APPLIED, not fetchable

A 200 on the woff2 proves nothing — a `font-face` can load and still be overridden. Prove
application in a real browser by measuring the same string against a generic fallback; **different
widths mean the face is really in use**:

```js
const c = document.createElement("canvas").getContext("2d");
const w = (f) => { c.font = f; return c.measureText("Astra chat 123").width; };
w('400 16px "DM Sans"') !== w('400 16px monospace')   // true => applied
```

Fetch the upstream CSS with a **mobile UA** or you get legacy TTF urls instead of woff2 subsets;
keep `unicode-range` and `font-display: swap` verbatim so glyph coverage is unchanged. Preload only
the above-the-fold faces — preloading all of them costs more than it saves.

**`grep -c` counts LINES, not matches.** Minified CSS is 2 lines, so 36 `@font-face` rules read as
`1` and look like a failed migration. Count occurrences (`grep -o … | wc -l`) before believing a
count on any build artifact.

### Block-memoized markdown: pin concatenation fidelity, and prefer ranges

Splitting into per-block memoized components stops the O(n²) re-parse, but the splitter can lose
characters — invisible in the splitter's own tests, obvious in the chat as a run-on paragraph or a
literal ``` fence. **Assert that concatenating all blocks reproduces the input exactly**, across
fences, unclosed fences, fence-inside-a-string, and unicode.

Then make it true by construction: emit **index ranges** into the original string and `slice` them,
rather than splitting strings and re-joining. String-splitting has to remember every separator
(every bug here came from exactly that), whereas ranges tile by definition. Add a `coversExactly`
guard returning `null` — falling back to the single-blob renderer — when ranges do not tile
`[0, len)`, so a bad split degrades to old behaviour instead of corrupting output.

A backtick run inside a fenced body is **content, not a closer** (CommonMark closes only on a fence
with no info string), so a check asserting "every block has paired fences" is wrong for that case.

**Verify the fix is on the hot path.** If the whole-blob render is still computed unconditionally
for the fallback, memoization buys nothing while every delta still pays the full parse.
Short-circuit it when blocks exist.

### Report green as a conditional, and prove authorship before fixing a peer's failure

A suite run while other sessions are mid-flight is a **conditional** result, not a pass. Say so
("52/52 with nothing else running"), or an unrelated concurrent failure reads as yours. When a check
fails, prove authorship before touching it — `git stash push -- <your paths>` then re-run. A failure
that survives with your changes removed belongs to a peer; the correct report says so rather than
fixing it inside your commit. Stage explicit paths, never `git add -A`, in a shared tree.