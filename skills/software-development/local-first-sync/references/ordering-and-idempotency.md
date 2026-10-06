# Ordering and idempotency — choosing a total order

Depth for the "what key do I sort by" and "how do I stop double-sends" decisions.
Read when implementing clause 5/8 of a sync brief, or when messages land in the
wrong place on one device.

## The order

```
KEY(committed)  = (0, server_cursor, row_id)
KEY(optimistic) = (1, uuidv7_ms, client_msg_id)
```

- Committed always sorts ahead of pending at the same instant, so an optimistic
  row can never jump ahead of — or behind — the reply it is waiting for.
- **No client wall-clock anywhere.** Timestamps are display-only.
- Dedupe by id **before** sorting. A reconnect can deliver the same row twice
  (socket replay + HTTP catch-up); without this a message renders twice.

### Why the industry rule is "server-side, always"

Slack's `ts` *is* the id and the sort key. Discord uses a snowflake (42-bit ms +
worker + process + counter). Telegram has a per-chat integer `message_id` and
treats `date` as display-only. Google Chat's `createTime` is output-only. The
unanimity is the finding: a phone whose clock is four seconds slow would otherwise
place its own message before one you actually sent later.

Check what the upstream engine already does before inventing a scheme — the answer
is often already written down in its source with the reason attached.

## UUIDv7 yes, hybrid logical clock no

RFC 9562 §5.7 mandates v7 for time-ordered ids; §6.4 concedes multi-node
generators lean on the random source. So **v7 makes tie-breaks stable, not
correct**. Correctness comes from the server's cursor; stability comes from the
client's uuid. Do not add an HLC.

### Reading fields out of a v7 id

The rendered form is `8-4-4-4-12` with dashes, so hex fields are at
`[0:8]`, `[9:13]`, `[14:18]` — **not** `[8:12]`. Slicing at 8 yields `"-4a4"`, and
`parseInt` on that returns a negative number that looks exactly like an encoder
bug. Bytes 0..3 carry `ms>>16`, bytes 4..5 carry `ms&0xffff`.

## Is the upstream cursor per-process?

The single highest-value question to ask before keying anything. Grep the upstream
for how it allocates the counter. If it lives in process memory, **it resets to 1
on restart** — the upstream usually ships a `replay_epoch` token precisely because
of this.

Consequences if it resets:
- `(id, seq)` is **not unique across a restart**; `INSERT OR IGNORE` drops every
  post-restart chunk. This is silent and looks like a clean run.
- A client resuming on that counter skips a whole post-restart turn.

Fix: per-process **epoch** in the primary key, own monotonic counter as the
cursor, keep the upstream's number as a returned field only.

Prove it with the real reset: log seq 1..3, simulate the reset, log seq 1..2
again, and assert all five survive.

## Truncation signalling

`truncated: true` means "there IS a hole — refetch history instead of splicing a
partial answer onto a gap." Splicing onto a gap renders a transcript that looks
complete while missing text, which is worse than an error.

- Set it only on **actual deletion** (a purge watermark), never on sparsity.
- False for a caught-up cursor, an unknown session, and a live session.

## Idempotency

At-least-once delivery, once-only effect. The client cannot distinguish
"accepted, response lost" from "never arrived" — only the server can.

```
claim(key)  ->  side effect  ->  return
```

- One statement (INSERT hitting a UNIQUE constraint). A read-then-write check lets
  two concurrent callers both win; assert this with a 20+ way concurrent race.
- On duplicate: acknowledge locally so the client clears pending state, and
  **return** — never fall through.
- **Any dedupe-store error forwards anyway.** A rare duplicate beats a lost
  message.
- Key on a client-minted uuidv7 that doubles as the resource identity. Without a
  client-supplied id, `POST` cannot tell success-with-lost-response from
  never-arrived.
- If the upstream ingest path can't yet accept a client id, the dedupe table lives
  in your own store — and say so, rather than assuming it works.

## Late-arrival splice

A message arriving after later rows were rendered must go to its true position,
not append. Report **which turn it splits** so the caller re-partitions from there
instead of re-deriving the whole transcript.

Two ordering bugs worth asserting directly:
- Scanning only same-kind turns misses the case that matters — a user message
  breaks an **assistant** turn, the opposite kind.
- Returning the *first* same-kind turn a row sorts after puts a trailing message
  mid-transcript; take the *last*.
