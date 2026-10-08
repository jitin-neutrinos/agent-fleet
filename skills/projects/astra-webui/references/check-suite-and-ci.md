# Check-suite health, regression gate, and CI

Applies to the `*.check.mjs` / `*.check.ts` convention (`src/lib/`, `server/`, `scripts/`): assert-based,
no framework, each file exits nonzero on failure. Depth for `references/publish-readiness.md` step 8.

## 1. Health audit — do the checks even RUN?

**Never assume a check file executes because it exists and reads correctly.** A check that cannot resolve
its imports throws at module load, prints a stack, and is indistinguishable in a CI log from a real
assertion failure unless you actually run the set.

```bash
R=0; F=0; FAILED=""
for f in $(find src server scripts -name '*.check.ts' -o -name '*.check.mjs' -o -name '*.check.tsx' | sort); do
  if node "$f" >/dev/null 2>&1; then R=$((R+1)); else F=$((F+1)); FAILED="$FAILED $f"; fi
done
echo "PASS=$R FAIL=$F"; for f in $FAILED; do echo "  $f"; done
```

### Pitfall: Node type-stripping strips types, it does not resolve specifiers

Running a `.ts` file directly on Node 22+ removes the types and then fails on **module resolution**, not
types. A check passes iff **every hop of its import graph** names the extension:

| Import style | Result |
|---|---|
| `from "./foo.ts"` | resolves — runs |
| `from "./foo"` | `ERR_MODULE_NOT_FOUND` — dead |

So the fix is not in the check file. `streaming-resilience.check.ts` imports `./hermes-ws.ts` *with* the
extension, yet still fails, because `hermes-ws.ts` itself imports `./connection-state` *without* one.
Grep the whole transitive graph, not the check's own import lines.

Prove the correlation before you fix anything — it separates this cause from a real assertion failure:

```bash
for f in src/lib/*.check.ts; do
  grep -qE 'from "\./[a-z0-9-]+\.ts"' "$f" && pat=HAS-EXT || pat=NO-EXT
  node "$f" >/dev/null 2>&1 && res=PASS || res=FAIL
  printf '%-45s %-8s %s\n' "$(basename "$f")" "$pat" "$res"
done | sort -k2,2 -k3,3
```

Only the import statements need the extension added; leave every other specifier and all logic untouched,
and re-run the audit to confirm the count moved to the expected total.

### Fix it with a resolve hook, not by mass-editing source

Adding `.ts` to ~84 extensionless import edges across ~25 source files is the obvious mechanical fix and
the wrong one: it is a huge diff over the whole app, and this tree is shared with concurrent agent
sessions that commit to the same paths. A dev-only ESM resolve hook revives the whole suite with **zero
source edits**, and the hook is never bundled so app behaviour cannot shift:

```js
// scripts/ts-resolve-hooks.mjs — retry a failed relative resolve against real extensions
const CANDIDATE_EXTS = [".ts", ".tsx", "/index.ts", ".mjs", ".js"];
export async function resolve(spec, ctx, next) {
  try { return await next(spec, ctx); }
  catch (err) {
    if (err?.code !== "ERR_MODULE_NOT_FOUND") throw err;
    if (!spec.startsWith(".")) throw err;
    // Build candidates from ctx.parentURL directly — see the two traps below.
    const candidates = [];
    for (const ext of CANDIDATE_EXTS) {
      try { candidates.push(new URL(pathname + ext, ctx.parentURL).href + suffix); } catch {}
    }
    for (const candidate of candidates) {
      try { return await next(candidate, ctx); } catch {}
    }
    throw err;
  }
}
```

Register it with a sibling `ts-resolve.mjs`: `register("./ts-resolve-hooks.mjs", import.meta.url)`, then
invoke checks as `node --import ./scripts/ts-resolve.mjs <check>`. Two traps, both of which manufacture
*fake test failures* while you are writing the hook — the symptom is a check that loads fine but asserts
the wrong thing, so you chase a phantom logic bug:

- **Insert the extension BEFORE any `?query`.** A cache-busting import (`./notify?legacy-shape`) must
  become `./notify.ts?legacy-shape`. Appending after the query yields `./notify?legacy-shape.ts`, the
  specifier resolves to the *already-loaded* module, and the test's "fresh module instance" premise
  silently evaporates — surfacing as a wrong-value assertion, not a resolution error.
- **Never round-trip through `url.origin`.** Once the parent is itself a `.ts` file URL its origin is the
  string `"null"`, and `new URL(path, "null")` throws `ERR_INVALID_URL` — so every second-level import
  dies. Construct candidates with `new URL(x, ctx.parentURL)` instead.

`import.meta.dirname` is NOT available on this Node; use `resolve(fileURLToPath(import.meta.url), "..")`.

### A runner over a green subset is worse than no CI

A workflow that runs 28 of 50 checks reports green while `canvas-schema`, `final-text`, `unread` and
`replay-dedup` sit permanently unverified — it manufactures false confidence about exactly the modules
(canvas, gates, segments) most likely to regress silently. **Revive first, then wrap.** Never ship a CI
gate over a subset without saying, in the run output, how many files were skipped and why.

## 2. Runner

One script, plain Node, no framework — matches the checks' own zero-dependency style.

- Discover by glob over the three roots; sort for stable output.
- Run each in its own child process; classify `ok` / `failed` / `skipped (unrunnable: <reason>)` so an
  environment gap is reported as its own class rather than as a pass.
- Aggregate: print per-file one-liners, then a `PASS=n FAIL=n SKIP=n` line, exit nonzero iff `FAIL>0`.
- Concurrency is fine and worth it — these are single-file runs, and a serial pass over 50 checks is slow
  enough to tempt people into skipping it. Bound it anyway so a hung child cannot wedge the gate.
- Keep the runner itself out of the glob's match pattern.

## 3. Regression gate

The upstream community project's strongest transferable idea: a permanent suite that pins **bugs already
fixed**, so the fix can never silently revert.

This repo's `*.check.*` names are already self-documenting as regression subjects — `chat-dedup`,
`replay-dedup`, `no-dup`, `final-text`, `safe-tail`, `request-ownership`, `unread`, `tab-isolation`,
`source-filter`. Two things make it a real gate rather than a name list:

1. **A manifest mapping each entry to the check file that guards it.** An orphan entry (a pinned bug with
   no check) and a dead check (a check that cannot run) fail the gate for opposite reasons, and only the
   manifest distinguishes them.
2. **The gate asserts the named check is in the passing set.** Pinning a bug name is worthless if the
   check protecting it is one of the 22 that cannot execute — which is exactly the state before step 1.

Derive the manifest from check names only when the owner has not reviewed it; where a name is ambiguous,
ask rather than invent the bug it corresponds to.

### The gate must fail BOTH ways, and must be loud about unpinned checks

Two failure directions, and the second is the one people forget. A gate that only checks "every pinned bug
has a live check" happily coexists with a brand-new check that guards nothing:

- **guard deleted or renamed** → the pinned bug silently loses its pin → fail.
- **check added but not added to the manifest** → it guards an unpinned bug and will never be required
  again → fail.

The second direction is what makes the gate earn its keep: on its first run it reported every check in the
repo that no manifest row claimed. Add a discovery step (glob the roots, diff against the manifest rows,
fail on any unmatched file) and the gate stops being a list that rots.

One row per **bug class**, not per check file — several distinct owner-reported bugs share a single
guarding check, and rows may name the same guard. Mark env-dependent checks `live: false` so they are
existence-checked but not executed; that is not the same as passing.

**An unpinned-file failure naming a file you did NOT write is a concurrency signal, not your bug.** This
tree is shared with live agent sessions, so a check can appear between your glob and your gate run. Do not
assume authorship: `git status`/`git log` the path, and if it belongs to another session, pin it with an
accurate row rather than deleting it or silently widening the gate. Pinning a peer's check costs one
manifest line; ignoring the failure breaks the gate for both of you.

**Proving the failure belongs to the other session — park-and-prove, then commit only your own paths (proven 2026-10-03).** The failing check named `config-page.tsx`, a file a sibling session had 481 lines of WIP in: `git stash push -- src/components/config-page.tsx`, re-run the gate → green; pop → red again. That flip is the proof; only then commit, and stage ONLY your own paths (`git add <your files>`, then `git diff --cached --name-only | grep -vE <your patterns>` must come back clean). After every pop, re-check `git status --porcelain <file>` — the ops run with output suppressed, so a silently-bungled pop hands you an empty tree and you have lost the sibling's WIP; recover with `git checkout stash@{0} -- <file>` + `git restore --staged <file>`. Two traps the same day cost real debugging time:

- **Stash source AND its check file as a PAIR.** Stashing `canvas-schema.ts` alone left the modified check file importing `extractOutermostJson` from a schema that no longer exported it — the suite died `not ok 1` with "does not provide an export named", which reads as a code bug, not a stash accident.
- **When bisecting variants by overwriting the file, snapshot each variant to scratch first and verify symbol presence after every restore.** A bisect script left the tree on the wrong variant; the suite then failed on a phantom missing export until `grep -c 'function <symbol>'` proved which variant was actually on disk.

## 3b. Coverage drift is its own finding

The gate's discovery step doubles as a completeness check on the repo. A count that moved without anyone
adding a check means the suite shrank — the workflow should fail on a floor (e.g. fewer than 40 discovered)
so a silently-empty suite cannot report green. Report `discovered` alongside `pinned` in the gate's own
output line; the two numbers diverging is the signal.

### A pinned bug that is FLAKY is worse than unpinned — fix the harness, do not loosen it

When reviving the suite, a check may fail intermittently. Do not exclude it from the gate and do not
relax its assertions: a check that claims to pin a fixed bug but fails 5-in-6 runs is publishing
unreliability about the very thing it certifies.

The failure is almost always in the harness, not the product. Two shapes, both found here:

- **A parent-side timer racing a background worker's cadence.** The fake upstream flipped DELETE
  500→200 after a fixed 500 ms settle while the sweeper retried every 200 ms — three retries landed
  inside the window, each answered 500. Fix: make the fake fail *exactly the first* attempt and answer
  200 thereafter, so no timer participates. Gate the failure on the **attempt number**, never on a
  boolean flag that stays true for the whole scenario — keying on the flag alone 500s every retry and
  converts a flake into a deterministic failure.
- **A poll sampling a TRANSIENT state.** The child waited for `awaiting_retry` mid-flight, but the retry
  period equalled the poll period, so the retry could land and reach `done` before the poll ever sampled
  the transient state; the loop then exited via its "not observed" branch. Fix: wait for the **terminal**
  state only, and prove the retry from a counter the harness owns (attempt count), which cannot be raced.

General rule: **assert on terminal states and harness-owned counters, never on a state a background worker
passes through.** To confirm the diagnosis before changing anything, instrument the fake and log each
call with its status and a timestamp — a sequence like `attempt=1 500 / attempt=2 500 / attempt=3 500 /
attempt=4 200` names the mechanism outright.

Then **prove the fix by repetition**: 10+ consecutive runs, not one green run. One pass after a timing
change proves nothing.

Ruled out before blaming product logic: orphaned SQLite `-wal`/`-shm` sidecars after `rmSync` (clean
`close()` checkpoints and removes them), leftover scratch dirs (`mkdtempSync` is unique per run), port
reuse (fake binds port `0`).

### N clean runs is not proof of a race — reproduce the failure on purpose

"It passed twice, must be a race" is how a real bug gets filed as noise. A flake reproduced
3-of-4 times needs a **deliberate overlap harness**: start a second instance of the same
check while the first is mid-flight and count failures. If the overlap fails 5/5 and serial
runs pass 3/3, the mechanism is real and worth 20 more minutes — do not ship "52/52 passing"
as a result when the honest statement is "52/52 whenever nothing collides". Same rule as the
assertion work above: prove the mechanism, then report the number you measured.

### A parallel runner and a gate that re-runs the same checks collide by construction

The gate re-runs guarded checks with `spawnSync` **while the worker pool is still running
them** — the same file, two processes, at once. Any check that binds a fixed port, writes a
fixed scratch path, or spawns a server will fail, and the gate reports it as
`REGRESSED: <file>`, i.e. as a product regression that never happened.

Diagnose by asking which resources are global rather than per-process: grep the guarded checks
for `listen(`, `createServer`, `PORT =`, `ASTRA_*_PORT`, and any scratch path they `rm()`
then re-seed. **The port is usually only the first of several** — fixing it can move a 5/5
failure to 1/5 and the remainder is a second resource, so keep enumerating until the overlap
is clean.

Fix by making every such resource a function of the **worker slot**, so two concurrent
instances can never target the same one:

- runner: `env: { ...process.env, ASTRA_CHECK_PORT_OFFSET: String(slot) }`, passing the slot
  index through the worker loop. `spawnSync` children inherit `process.env`, so the gate's
  re-runs pick up the gate's own slot offset with no change to the gate at all.
- each check: base port + offset, and the scratch filename + offset.
- keep any documented manual dodge var working by accepting both names
  (`process.env.NEW ?? process.env.LEGACY`), or you break the remedy printed in the error.

**Verify with the overlap harness, not the suite.** Prove it with the same overlapping pairs
that used to fail, awaited so you are not measuring `TIME_WAIT`, and assert both halves: zero
failures AND zero orphaned listeners afterwards (`ss -ltnp | grep <port>`). A pass rate alone
hides a child the check never reaped.

### A check that spawns a server must reap it on EVERY exit path

Cleanup at the end of `main()` does not run when the check exits early — `process.exit(2)`
from a preflight assertion, an uncaught throw, a signal. The child survives holding its port,
and the *next* run collides with a stranger that answers its health probe, so every assertion
silently tests the wrong process. That is self-inflicted: the check manufactures the exact
"orphaned child from an earlier run" its own guard comment warns about. Register the child in
a module-scope handle and reap from `exit`/`SIGINT`/`SIGTERM` handlers plus the `main().catch()`.
When a preflight guard reports `EADDRINUSE`, check for orphans first — the cleanup bug is the
real defect and the guard is the symptom.

## 4. CI workflow

Node-only checks mean **a version matrix buys far less than it does for a multi-version Python project** —
the checks exercise repo logic, not interpreter-specific behaviour. One pinned Node version plus the real
gates is the honest shape:

1. checkout → setup-node (pinned) → `npm ci`
2. `node scripts/run-checks.mjs` — the assertions
3. `npm run build` — the `tsc -b && vite build` gate (`tsc --noEmit` is a no-op here; see publish-readiness)
4. `npm run lint` — `oxlint`
5. smoke job: the deployment script against a live build

Keep `run-checks` as its own step so a failure names the stage. Add the new dist bundles and canvas
components to the template-literal route extractor (harness check 24) in the same commit that adds them,
or the gate silently stops seeing them.

### A gate that is RED on its first push is worse than no gate

Running over a subset (§1) and landing red are different failures, and only the first is obvious. Before
declaring CI done, execute every step **exactly as the workflow will** and read each real exit code —
`npm run lint` exits nonzero when a single pre-existing error remains, so adding a lint step to a tree
with one old error ships a gate that fails on its first run and is muted by everyone forever.

The failure belongs to the workflow, not to the old error. Either fix/baseline the pre-existing error in
the same change, or do not gate on that step yet. Prove the pre-existing-ness honestly (lint the file as
committed at HEAD, or stash your config edit and re-run — §5) — but "it was already there" is a reason to
fix or defer, never a reason to ship red.

Verify the gate against the artifact CI actually receives, not your working tree: `git archive HEAD | tar
-x` into a scratch dir, symlink `node_modules`, build there. A tree carrying untracked source files passes
locally and fails the clone — so the build step you are still writing is the one that would have caught it.

### An assertion that matches its own failure output is a no-op

A smoke step shaped `import(x).catch(e => print("loaded-or-failed"))` followed by
`grep -q "loaded-or-failed\|loaded"` **always passes**: the catch arm prints one of the two strings the
grep accepts, so the step confirms its own guard fired rather than that the module loaded. Same class as
a probe that manufactures a bug (§5). Make success and failure paths mutually exclusive, and if a step
swallows an error it must swallow the exit code too.

### A green check on a function nothing calls certifies nothing

A helper exported, unit-tested, and imported by zero application call sites produces a passing assertion
that cannot fail in production — the suite reads as coverage while exercising dead code. After extracting
a helper for testability, grep for its callers and either route the real call site through it or drop the
export. A contract with no consumer is a comment.

## 5. Parity gate — port-or-replace protocol

Owner standing rule: **capture a baseline first; only swap the current implementation once parity passes
and the new output is at least identical.** Applies to any port, refactor or swap in this repo.

1. **Baseline before touching anything.** For check work that is the full pass/fail table plus the exact
   output of every previously-passing check. For a UI or transport change it is the observable behaviour —
   frame contract, rendered result, timings.
2. **Make the change.**
3. **Re-run the identical command.** Compare like-for-like: same runner, same files, same flags.
4. **Ship only on: every previously-passing check still passes, every revived check passes, and the new
   output is equal or better.** Better means a real measured improvement, not a claim.
5. Anything less is reported, not swapped.** State which criterion failed and by how much. A partially
   passing port stays unmerged rather than landing as a silent regression.

**Re-verify the parity baseline after the change, do not reuse the first run's numbers.** A count taken
before the change and a count taken after it are only comparable if the *set* of discovered files is
identical. Glob early and often: a runner that walks the whole repo will pick up archived copies under
`.audit-evidence/`, snapshot fixtures and vendored bundles, and report a larger total than the baseline
it is being compared against. Skip dot-directories and archive/snapshot roots explicitly.

Also check the linter for the same blind spot: a lint config that does not ignore `scratch/` will fail on
committed scratch bundles and bury the real signal. Confirm lint's error count is **unchanged** by your
work (stash your config edit and compare) before claiming lint parity — a pre-existing error that was
merely hidden by noise is still an error.

## 6. Before porting from another project: verify the advantage runs BOTH ways

Reading the other repo's `ARCHITECTURE.md` and source is the only way to know what it actually does — the
README describes intent, and intent diverges from the code. Then check **which side is ahead**, because
the intuitive read is frequently backwards, and porting the "better" implementation inverts into a
regression.

Concrete instance: the upstream Hermes web UI runs the agent in-process over SSE with a `queue.Queue`
registry and inline approval push — elegant, and its own docs carry a critical concurrency warning
(process-global env vars clobber each other across concurrent requests) plus an admitted gap where
agent-loop delegation is unshipped. Astra's bidirectional WebSocket engine with resume, liveness recycle,
a turn watchdog and a durable offline queue beats it outright, because SSE cannot express any of those.
The portable items from that project were its **process** assets — test volume, CI shards, ADR/discipline
docs, the regression gate — never its transport or its in-process model.

So: enumerate candidates, verify each against the local implementation, and say plainly which direction
wins. Report "do not port" as a finding; it is the outcome that protects the codebase.

## 7. Reporting a full fix-verification audit ('are my chat bugs fixed?')

When the owner asks whether previously reported bugs are actually fixed, verify per fix, then report —
never re-narrate the bug reports:

1. **Grep each fix signature in source AND each deployed bundle** — `dist/assets/index-*.js` and the
   APK bundle `android/app/src/main/assets/public/assets/index-*.js`. A fix in source only is not a fix;
   report a source-vs-bundle mismatch as "fixed-in-code, not shipped to your device".
2. **Date the artifacts first**: commit time (`git log -1`), dist mtime, APK bundle mtime. The phone's
   WebView loads the server dist over the tunnel, so server-side fixes reach the phone without an APK
   rebuild — an APK older than the fix commits explains most "not fixed" reports.
3. **Probe the live server with real auth** (login → session cookie) and confirm the server-side data
   behind the symptom — e.g. the sessions list actually returns the row the owner says is missing, with
   the correct `sources=` filter — before diagnosing client code.
4. **Run `npm run check` and classify failures.** A regression-gate failure listing DUPLICATE `RG-\d+`
   ids is repo hygiene (two sessions pinned different bugs under one id — re-id the second set), not a
   product regression. An interpreter/SQLite version failure is an environment constraint, not app code.
   The gate refuses duplicate ids wholesale, so ONE dupe row turns the whole gate red — distinguish its
   failure class before reading it as 129 real regressions.
5. **KNOWN environment failure (2026-10-08): `sqlite-runtime.check.mjs` fails on Node v22.22.2**
   ("SQLite 3.51.2 is vulnerable to the WAL-reset bug (fixed in 3.51.3)"), which also paints the
   regression gate red (1 failure = this check crashing). Verified pre-existing via clean-tree
   stash-isolation — any diff present at the time is NOT the cause. Fix is a Node interpreter
   upgrade on the host (Node 24.9 bundles only 3.50.4, so verify the bundled version, never the
   Node number); until then treat this one check as a known-red environment constraint.
6. **Report verified vs inferred separately, per row** — bundle grep + live curl for what was proven,
   ranked verdict for what was inferred. State which artifacts (APK, dist, tunnel) each verdict depends on.
