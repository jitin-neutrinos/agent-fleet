# Diagnosing "slow stream" and "chat open takes seconds"

Class of work: a user reports the chat feels slow, or opening a chat shows a
skeleton for a couple of seconds. This file is the measurement procedure. It is
built around one rule:

## RULE: measure before touching anything, and A/B your own recent work first

A slow-chat report after you just shipped work is an accusation until proven
otherwise. Measure your own change's cost against the budget BEFORE defending
it, and say the number in your report — "my change costs 0.10 ms of a 33 ms
frame" is a fact; "my change is unrelated" is a claim.

Steps in order. Do not skip to the fix.

### 1. Cost your own recent work against its budget

For a per-frame/per-request hot path, microbenchmark your own code on realistic
input and express it as a fraction of the budget it shares.

- Streaming frames arrive at ~30/sec (33 ms window). Cost your per-frame work as
  `per_frame_ms * 30` and compare to 33 ms.
- Anything under ~1% of the budget is not the cause; say so and move on.

### 2. Measure the server alone, authenticated

Measure each route the client actually calls, locally (`127.0.0.1:3011`), with
a real session cookie, median of 4+ samples (not a single cold hit):

- baseline `/api/health` — this is pure server overhead, everything else is signal
- the sessions list
- the history page (this is the skeleton gate)
- any metadata/title route

If the server answers in single-digit-to-low-tens of ms, the server is NOT the
cause and you should say so before looking client-side.

PITFALL: the sessions list field is `id`, not `session_id`. A KeyError here looks
like a broken endpoint when it is just a wrong key.

PITFALL: a `Secure` session cookie will not travel over plain HTTP, so a
`urllib`/`curl` call to the public hostname returns 403 even with a valid token.
Measure public-hostname latency from inside the browser, not from a script.

### 3. Measure the tunnel separately — it is usually the biggest single number

Compare the SAME route local vs through the tunnel. On a Cloudflare-fronted
personal app this gap is commonly 100–300 ms per request and it multiplies by
every duplicated call. Establish it early: it changes which fix matters most.

### 4. Count the fetches, not just their latency

Hook `window.fetch` in the page and log every call with URL, duration and body
size. Duplicate requests across independent call sites are invisible to per-route
timing — three components each fetching the same list cost 3x and look like one
slow route.

PITFALL: `el.click()` and synthetic `MouseEvent` dispatch frequently do NOT
reach a React onClick handler. Use the real coordinate click
(`click_at_xy`) on a live `getBoundingClientRect()`. Also re-read the
coordinates immediately before clicking — an earlier `scrollTop` write invalidates
them, and clicking stale coordinates lands on the search box or a panel header
and silently does nothing.

PITFALL: verify what is actually at the coordinates with `document.elementFromPoint`
before concluding the app is broken. A dead click and a broken handler look
identical from the waterfall (zero requests).

### 5. Audit payload weight against what the client actually reads

For each response, compute per-key byte totals, then grep the client for each
key. Unused heavy keys are pure waste. Common offenders on a proxied chat
backend: `system_prompt` and `tool_names` on a session record (~150 KiB) when the
client wants a 46-byte title; `api_content` duplicating `content` on every
message row.

### 6. Attribute the remainder to the main thread

Sample `document.querySelectorAll('*').length` across the open window to get the
DOM growth, and use `PerformanceObserver({entryTypes:['longtask']})` to separate
network from transform/render.

PITFALL: a `requestAnimationFrame` probe that "times out" is usually the CDP
transport blocking on a promise, not evidence the main thread is saturated.
Confirm with a bounded busy-loop probe — if it returns in approximately its own
budget, the main thread was NOT blocked and the timeout was instrumentation
noise. Do not report "the renderer is saturated" from a timeout alone.

### 7. Rank fixes by measured contribution, largest first

State the phase breakdown as a table (wait-on-duplicates / wait-on-fat-payload /
wait-on-network / render) with the measured ms for each, so the user can approve
a specific slice. Do not implement before approval when the user asked for an RCA.

## Frequent real causes, in the order they were found

1. **The same list fetched from N independent call sites.** Grep for the endpoint
   across `src/` — sidebar, app root, and a maintenance/prune module each fetch
   independently with no shared cache. Largest single win, cheapest fix.
2. **A metadata route returning an entire session record.** A title request that
   ships the system prompt and tool definitions is ~150 KiB of pure waste.
3. **History page size.** 100 rows at a time, half of it tool output that renders
   collapsed. Drop unused duplicated fields first; virtualising the transcript is
   the largest win but the most invasive.
4. **Tunnel RTT multiplied by request count.** Not a code bug; report it so the
   user knows the floor.

## Reporting shape for this class

- State reproduction first, with the measured number ("skeleton visible ~2,520 ms").
- State plainly whether you caused it, with the measurement that proves it.
- Table: root cause -> evidence -> cost.
- Ranked fix list with an explicit "nothing changed yet" line, and ask for approval.
- Separate what you measured from what you could not (e.g. the native app path).