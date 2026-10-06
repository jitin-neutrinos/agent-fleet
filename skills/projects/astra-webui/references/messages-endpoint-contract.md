# `/api/sessions/<sid>/messages` — the paging contract, and reading it honestly

## The endpoint

`GET /api/sessions/<sid>/messages?order=&limit=&offset=&include_compacted=`

- `order` ∈ `oldest` | `latest`. It **ALWAYS pages** — an omitted `limit` does not
  mean "everything", it means the newest 500 (`limit` is capped at 500).
- `offset` walks from the anchor implied by `order`.
- The reply carries a `pagination` block (`limit`/`offset`/`order`/`returned`).

Two anchors, opposite directions — mixing them is the whole bug class:

| `order` | anchor | `offset=N` walks | use for |
|---|---|---|---|
| `latest` | NEWEST row | BACKWARD through older rows | a tail page + scroll-up backfill |
| `oldest` | OLDEST row | FORWARD through newer rows | streaming a transcript from the start |

**`order=oldest` + `offset=<rows already held>` re-fetches rows you already
have** and dead-ends backfill. `chat-landing.tsx` therefore pins `order=latest`
and derives `offset` from the held-row count. The pure contract lives in
`src/lib/pagination.ts` (`pageRequest` / `pageOffset` / `hasMore` /
`prependOlder`) so the invariants are checkable — see `pagination.check.ts`.

Two more invariants worth keeping, both of which the check pins:

- **Dedupe is id-keyed, and id-less rows are never deduped against each other.**
  The boundary row is commonly re-sent; rows with no id carry no durable
  address, so collapsing them drops real content.
- **`hasMore` treats a non-array / negative / undefined return count as
  exhausted.** A short page means the end; a bad count must terminate
  pagination rather than loop forever.

## Every page is internally ascending; pages descend against each other

Page 1 (`order=latest`) is the newest 200 in chronological order. Page 2 is the
200 rows *above* it, so its ids are all LOWER than page 1's. Cross-page descent
is correct and expected — the UI prepends page 2 above page 1.

**When probing this, assert ordering WITHIN a page and id-uniqueness ACROSS
pages.** A probe that compares ids across the page boundary reports every
newest-first page as "out of order" and manufactures a bug that isn't there.

## Read the endpoint before declaring a capability missing

An earlier pass recorded "pagination is blocked on the gateway" because
`session.resume` exposes no `limit`/`offset`. That was checked on the WRONG
transport. Two facts settle it:

- `session.history` (WS) returns the whole transcript with no paging params at
  all — it is not a paging surface.
- The **REST** `/messages` route pages properly, and this repo already used it
  that way elsewhere: `server/training.mjs` walks a 450-row dump through it.

So the rule: **before calling a gateway capability absent, grep THIS repo's own
server code for an existing caller of it.** A working consumer in-tree is
stronger evidence than the RPC contract you happened to read. Declaring a
shipped feature missing costs the owner a false "it's broken" report and a
rewrite of working code.

The same pass had the feature *working* and still improved it — not by adding
capability, but by extracting the invariants out of a 2,000-line component
into a checkable module. "Already built" is a finding to report, not a reason to
stop: the deliverable becomes the contract + its assertions.

## Proving a paging change against live data

Page a real long transcript (a 400+ message session) and assert: rows seen ==
reported count, unique ids == rows seen, intra-page ascending, no unexpected
page-boundary ascent. That is a real receipt; a green unit check on the helpers
proves only the arithmetic, never that the host honours `order`/`offset`.

Related: `references/check-suite-and-ci.md` (runner + regression gate),
`references/hermes-wiring.md` (auth traps, streaming, media).
