# Proxy-side session-row enrichment

How to add a field to the chat sidebar's session rows without editing the Hermes checkout.

## Why the proxy owns this

`~/Work/projects/astra-webui` ships **zero** edits to `~/.hermes/hermes-agent` — that
is the whole point of the repo (so `hermes update` can never erase the UI). When the
gateway's row shape is wrong for a product requirement, the fix goes in
`server/hermes-proxy.mjs`, never upstream.

## The hook

`proxyRest()` already buffers the sessions list/search response to re-serialize it
(read markers). That buffer is the enrichment seam:

```js
if ((isSessionsList || isSearch) && proxyRes.statusCode === 200) {
  const chunks = []; for await (const c of proxyRes) chunks.push(c);
  try {
    const data = JSON.parse(Buffer.concat(chunks).toString());
    const rows = data.sessions || data.results || null;
    if (Array.isArray(rows)) {
      enrichSessions(rows);              // unread / last_read_at (read-state.mjs)
      await enrichLastReplies(rows, { cookie });  // last_reply (last-reply.mjs)
      res.writeHead(200, {...}); res.end(JSON.stringify(data)); return resolve();
    }
  } catch (err) {
    console.error("[hx] sessions enrich failed, serving raw rows:", err?.message || err);
  }
  const raw = Buffer.concat(chunks);      // fall through raw
  ...
}
```

**Never leave that `catch` silent.** A swallowed throw here presents as "the feature
just doesn't work" across multiple deploys, because the route still 200s with
well-formed rows.

## Pass the caller's cookie

`enrichLastReplies(rows, { cookie })` reuses the upstream session cookie
`proxyRest` already obtained via `getHermesCookie()`. Do NOT call `getHermesCookie()`
from the new module: that lives in the proxy and importing it back creates a cycle.
Also import node's http with the **named** binding —
`import { request as httpRequest } from "node:http"` — a default import resolves to
`undefined` under ESM and throws `httpRequest is not a function` at call time, which
the silent catch then ate.

## Cost control

One upstream call per visible row is only affordable if cached. Cache per session id
and invalidate on the row's activity stamp:

```js
const hit = cache.get(sid);
if (hit && hit.at === activityAt) return hit.text;   // activityAt = last_activity_at ?? last_active
```

Bound it: `rows.slice(0, max)` (max 12) so a 100-row page never fans out into 100
calls, an in-flight map so concurrent list renders dedupe, and a cache cap that
drops the oldest insertion (Map preserves insertion order). Rows past the bound keep
whatever the gateway sent; the client falls back.

## Gateway row-content traps (verified in `~/.hermes/hermes-agent`)

- **`preview` is the FIRST user message, forever.** `_PREVIEW_RAW_SUBQUERY_SQL` is
  `ORDER BY m.timestamp, m.id LIMIT 1` filtered to `role='user'`. It is not a
  "latest activity" field and never will be. For "show me the latest response",
  derive it.
- **`order=latest` pages back from the newest row but returns CHRONOLOGICAL order.**
  From `hermes_state_messages.get_messages`: *"latest pages back from the newest but
  returns chronological order."* The newest message is the **LAST** array element —
  iterate from the end. Getting this backwards silently returns the oldest response
  and looks like a data problem, not a logic one.
- **A narrow window finds no prose in a tool-heavy turn.** Tool-call turns are rows
  of `role=assistant` with `tool_calls` set and **empty `content`**, interleaved with
  `role=tool` result rows. `limit=8` can be entirely tool traffic → empty preview →
  silent fallback. Scan ~40 rows and cap the response body (~4 MB) so a pathological
  transcript cannot blow up the list request. Empty result is an acceptable answer
  (client falls back to `preview`).

## Test it

Pure-function tests pin the parse (`server/last-reply.check.mjs`): newest-response
selection, skipping tool/scaffold rows, falling through a tool-only newest row, the
three content field shapes, the length cap, and empty/malformed input. A test that
assumed newest-first ordering is what caught the reverse-iteration bug — write the
"newest is last" case explicitly.

Then verify end-to-end through the authenticated route (a unit test cannot prove the
field reaches the client): log in at `http://127.0.0.1:3011/api/login`, GET
`/api/hx/sessions?limit=5&order=recent` with the cookie, print `last_reply` per row.
`<<MISSING>>` = the enrich branch never ran.
