# Free-tier LLM gateways: what actually works

Findings from probing opencode-go and OpenRouter directly. The rewriter stage
that used these was removed, so nothing in the router calls them today — but
the findings are expensive to rediscover and apply to any future free-tier
model call (a judge, a label collector, a rewriter that comes back).

## The two headers that are not optional

A plain OpenAI-shaped POST to either gateway fails in a way that looks like a
credential problem and is not.

| Symptom | Actual cause | Fix |
|---|---|---|
| `HTTP 403` body `error code: 1010` | Cloudflare bot rule, before auth | send a browser `User-Agent` |
| `HTTP 400` `MissingSessionID` | opencode-go session requirement | send `X-Session-Id: <any stable id>` |

After both headers, the same key and model that returned 403 returns a normal
completion. **Never read a 403 from these gateways as "the key is wrong"** —
check the User-Agent first. It cost a long detour to conclude the key was
invalid when it was Cloudflare all along.

- opencode-go: `https://opencode.ai/zen/go/v1/chat/completions`, key from
  `OPENCODE_GO_API_KEY`, headers `User-Agent` + `X-Session-Id`.
- OpenRouter: `https://openrouter.ai/api/v1/chat/completions`, key from
  `OPENROUTER_API_KEY`, headers `User-Agent` + `HTTP-Referer` + `X-Title`.

## HTTP 200 with an empty body is the real hazard

Identical rewrite requests: 4 real answers, 1 empty. Across models, most free
tiers returned `200` with no content after 4-11 s. A success check that only
looks at the status code treats these as successes and the caller silently
falls through to a later fallback.

- Classify the outcome, do not just the status: `ok` / `empty` (200, no content)
  / `timeout` (queued) / `error` (4xx, auth, 404).
- **`empty` is transient, not fatal.** It must get the *shortest* backoff —
  retry immediately in the same turn. Banning a model for one empty response
  retires the only model that works, and the stage then starves itself and
  degrades to a paid or different provider.
- Back off a genuinely broken model (404/403/auth) for minutes-to-hours; back
  off a merely slow one for seconds. Persist the state to disk: an in-process
  dict dies with the hook process and buys nothing.
- A `200`-with-empty-model must not reset a healthy model's history, and must
  not count as an answer in any success metric.

## Toy-request latency does not transfer

Probing with `"Reply with exactly: OK"` produced a completely different ranking
than probing with the real prompt. One model answered the toy in 0.62 s and then
needed 10.2 s for the real rewrite. Free tiers **queue**, and queue depth
dominates.

- Measure every candidate with the **real payload**, not a short probe.
- Order the candidate list by the real-payload measurement, not the probe.
- Expect a free tier to have no reliable latency; bound the whole search with a
  wall-clock deadline and let it degrade to "no answer" rather than hang.
- Discover free model ids from the provider's own catalogue endpoint filtered on
  zero pricing. Guessing `:free` ids 404s almost universally.

## Practical upshot

If a stage needs a model call on a hot path, the free tiers will not hold a
latency budget. Use them off the critical path, or budget for their worst case
and design the stage to be skippable.
