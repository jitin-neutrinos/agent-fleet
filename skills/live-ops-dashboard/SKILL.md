---
name: live-ops-dashboard
description: "Build live ops dashboard pages with a zero-dep node backend."
---

# Live Ops Dashboard Pages

## When to use
When building dashboard pages that display live system health, stats, and status from multiple backend services. The browser cannot reach loopback services directly — the server must probe them and aggregate.

## Architecture

```
browser (React page, polls Ns, pauses when hidden)
   │  GET /api/{topic}
   ▼
server.mjs  ── cookie gate ──►  {topic}.js  handle{Topic}()
                                                │  TTLCache + in-flight dedup
                                                │  every probe = Promise.allSettled
                                                │  each wrapped in raceTimeout(2500ms)
      ┌─────────────────────────────────────────┼──────────────────────────────┐
      ▼                                         ▼                              ▼
loopback HTTP (node:http)              fs reads (node:fs)               child_process
```

## Server module pattern

### Bounded concurrency
```js
export async function raceTimeout(ms, label, promiseFn) {
  let timeoutId;
  const timeoutPromise = new Promise((resolve) => {
    timeoutId = setTimeout(() => resolve({ ok: false, error: new Error(`Timeout: ${label} exceeded ${ms}ms`) }), ms);
  });
  try {
    const result = await Promise.race([
      promiseFn().then(v => ({ ok: true, value: v })).catch(e => ({ ok: false, error: e })),
      timeoutPromise
    ]);
    return result;
  } finally {
    clearTimeout(timeoutId);
  }
}
```

### Single-flight dedup
```js
const inFlight = new Map();
async function singleFlight(key, fn) {
  if (inFlight.has(key)) return inFlight.get(key);
  const promise = fn().finally(() => inFlight.delete(key));
  inFlight.set(key, promise);
  return promise;
}
```

### Upstream fetch with cookie reuse
```js
async function fetchUpstream(apiPath) {
  try {
    let cookie = await hermesCookieOrNull();
    let res = await doRequest(apiPath, cookie);
    if (res.statusCode === 401) {
      clearHermesCookie();
      cookie = await hermesCookieOrNull();
      res = await doRequest(apiPath, cookie);
    }
    return { ok: res.statusCode >= 200 && res.statusCode < 300, data: res.data, statusCode: res.statusCode };
  } catch(err) {
    return { ok: false, error: err.message || "connection error", statusCode: null };
  }
}
```

**TRAP:** `raceTimeout` wraps `fetchUpstream`, so callers get `{ok: true, value: {ok: true, data: actualData}}`. The actual payload is at `.value.data`, not `.data`.

### Status vocabulary
Exactly: `healthy` · `degraded` · `auth-gated` · `unreachable` · `disabled` · `inactive`

```js
export function classifyHttpStatus(code, errCode) {
  if (errCode === 'ECONNREFUSED') return 'unreachable';
  if (code >= 200 && code < 300) return 'healthy';
  if (code === 401 || code === 403) return 'auth-gated';
  if (code >= 500 && code < 600) return 'degraded';
  if (!code && errCode) return 'unreachable';
  return 'degraded';
}
```

## Frontend pattern

### Polling hook
```ts
export function useOpsPoll<T>(url: string, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function fetchOnce() {
      try {
        const res = await fetch(url);
        if (!alive) return;
        if (res.ok) {
          const json = await res.json();
          if (alive) setData(json);
        } else {
          if (alive) setError(`HTTP ${res.status}`);
        }
      } catch (e: any) {
        if (alive) setError(e?.message || "fetch error");
      }
    }

    fetchOnce();
    timer = setInterval(() => { if (alive) fetchOnce(); }, intervalMs);

    function onVis() {
      if (document.visibilityState === "visible" && alive) fetchOnce();
    }
    document.addEventListener("visibilitychange", onVis);

    return () => {
      alive = false;
      if (timer) clearInterval(timer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [url, intervalMs, refreshKey]);

  return { data, error, refresh };
}
```

### Shared status components
```tsx
export const STATUS_META: Record<OpsStatus, { label: string; dot: string; text: string }> = {
  healthy:     { label: "Healthy",     dot: "bg-violetx",  text: "text-violetx" },
  degraded:    { label: "Degraded",    dot: "bg-fuchsiax", text: "text-fuchsiax" },
  "auth-gated": { label: "Auth-gated", dot: "bg-cyanx",    text: "text-cyanx" },
  unreachable: { label: "Unreachable", dot: "bg-redx",     text: "text-redx" },
  disabled:    { label: "Disabled",    dot: "bg-muted",    text: "text-muted" },
  inactive:    { label: "Inactive",    dot: "bg-muted",    text: "text-muted" },
};
```

**`violetx` IS the brand green (`#34d399`) despite its name.** Do not "correct" it to purple.

## Reading Hermes stores from node:sqlite

When a page must report on a store rather than a health JSON, probe SQLite directly.
Three traps, each of which produces a wrong-but-plausible number rather than an error:

- The export is **`DatabaseSync`**, not `Database`. Open read-only —
  `new DatabaseSync(path, { readOnly: true })` — because a status endpoint must never
  be able to mutate the store it reports on. Assert that guarantee in the check: open
  read-only and verify a write raises.
- **Every query must run before `close()`.** A query issued afterwards does not
  throw "no such table"; it silently returns `undefined`, so `?.count ?? 0` renders a
  confident `0`. Collect into locals first, then close.
- Intermittent `unable to open database file` on the `file:…?mode=ro` URI is WAL lock
  contention with a live writer, not a bad path. Retry with a busy timeout. (Diagnose
  it by trying all three forms: plain path, `file:` without mode, and `mode=ro`.)

What made these pages useful in the first place: the defects worth surfacing live in
the tables, not in any health endpoint — dead trust scoring, an unrecorded
`retrieval_count`, runtime framing stored as user memory, provenance coverage. A
dashboard reading only `/health` shows all-green while the store is quietly broken.
Derive counters that reflect *behaviour* (did anything ever get retrieved?) and not
just liveness.

## Data-truth rules

These are hard requirements when displaying live data from multiple backends:

1. **Known-broken aggregate rows:** If a backend's combined/summary row reports impossible values (e.g. `$0.00` cost with zero output tokens while per-item rows carry real numbers), render the per-item rows as authoritative and label the aggregate as unreliable. Never show the broken aggregate as if it were true.
2. **Hardcoded flags:** If a backend's "installed" or "healthy" flag is hardcoded in the collector (not measured), label it as such. Never present it as a live measurement.
3. **Null vs zero:** If a backend returns `null` for a count (meaning "not probed"), render "not probed" — never "0".
4. **Auth-gated services:** If a service returns 401/403, render `auth-gated` with a reason — never `unreachable` or red.
5. **Over-budget indicators:** If a store exceeds its budget, render the true percentage (uncapped) with an "over budget" tag. The progress bar may clamp at 100% width, but the number never clamps.
6. **Values over 100%:** If a percentage can legitimately exceed 100 (e.g. cache reads exceeding paid input), render raw — no clamping.

## Verification

```bash
# Pure-logic self-check
node server/{topic}.check.mjs

# Syntax check
node --check server/{topic}.mjs

# Build (separate call from any file mutation)
timeout 240 npm run build

# Restart + health check
systemctl --user restart {service} && sleep 2
curl -s http://127.0.0.1:{port}/api/health

# Endpoint test with minted session
JAR=$(mktemp)
curl -s -c "$JAR" -X POST http://127.0.0.1:{port}/api/login -H 'content-type: application/json' -d "{\"password\":\"$ASTRA_WEBUI_PASSWORD\"}"
T=$(awk '/astra_session/{print $NF}' "$JAR")
curl -s -H "cookie: astra_session=$T" "http://127.0.0.1:{port}/api/{topic}"

# DOM check
ASTRA_WEBUI_PASSWORD="$ASTRA_WEBUI_PASSWORD" node scripts/{topic}.dom.check.mjs
```

## Pitfalls

1. **`raceTimeout` + `fetchUpstream` double-wrapping:** `raceTimeout` returns `{ok, value}`, and `fetchUpstream` returns `{ok, data}`. When `raceTimeout` wraps `fetchUpstream`, callers must use `.value.data` to reach the actual payload. Using `.data` directly returns `undefined`.

2. **Pre-existing build errors block everything:** If `npm run build` fails due to errors in files you didn't touch, fix them first (even if trivial) — the bundle never generates and no page can render.

3. **`process` is not defined in browser context:** When using `page.evaluate()` in Playwright, pass Node.js variables as arguments: `page.evaluate(async (pw) => { ... }, process.env.PASSWORD)`.

4. **Strict mode violation in DOM checks:** If a selector matches multiple elements (e.g. a pre-existing `aria-live` element), tighten it: `[aria-live="polite"]:not(.sr-only)` or use `.first()`.

5. **`.mjs` files don't accept TypeScript type annotations:** Use plain JS in `.mjs` files — no `(param: any)` annotations.

6. **Memory store entry separator:** Hermes memory stores use `§` as the entry separator, not `\n\n`. Splitting on `\n\n` gives 1 block instead of the real entry count.

7. **Budget constants:** Memory budgets (`MEMORY_BUDGET_CHARS = 2200`, `USER_BUDGET_CHARS = 1375`) mirror the Hermes memory tool's own declared limits. If the tool's limit changes, update the constants.

8. **Skill files are user-owned:** The `astra-webui` skill is user-owned and cannot be edited by the agent. Recommend `hermes curator adopt astra-webui` for updates.

9. **A page that renders nothing, with no console error, is usually a rejected lazy chunk — not a data problem.** When a `lazy(() => import(...))` panel 404s (stale tab asking a new build for rotated content-hashed filenames), the rejection is ASYNC: nothing throws during render, `<Suspense>` shows its fallback and stays there, and the error boundary never fires. Prove the data is fine first — parse the exact stored payload, then `renderToStaticMarkup` it per block, then check `sanitize`-style transforms kept every block. If all three pass, the fix belongs on the import promise (`import(...).catch(err => { if (isStaleChunkError(err)) reloadOnce(); throw err })`), not in the boundary. Serving `/assets/**` as `immutable` while `index.html` is `no-cache` is correct for hashed names and produces exactly this silent-blank symptom for a stale tab; verify every lazy chunk's own imports resolve over HTTP before concluding anything else.

10. **When probing with `tsx`, the classic JSX runtime lies to you.** A probe that fails `React is not defined` for every component is a harness artifact, not a renderer crash. Add `/** @jsxImportSource react */` AND `globalThis.React = React`, or you will debug a renderer that is fine.

11. **`process.env` is absent in browser-context evaluation.** Pass Node-side values as arguments to `page.evaluate(fn, arg)`; inlining them breaks or silently reads a different scope.

12. **Reading a password to test an authenticated endpoint: take it from the live process environment, never echo it.** `tr '\0' '\n' < /proc/<pid>/environ | grep -m1 '^ASTRA_WEBUI_PASSWORD='` keeps the secret out of the transcript and out of any shell history.

<!-- canvas-output:start -->
## Canvas output

Plan in editable cards: a `spreadsheet` for the task table the reader will adjust, a `document` for the spec, `steps` for the sequence, `progress` for budget, `timeline` for milestones, and a warn `callout` naming the riskiest assumption.
<!-- canvas-output:end -->
