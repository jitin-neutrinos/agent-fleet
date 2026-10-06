# Auditing a memory / context subsystem

Probes and baselines for checking whether a memory, compaction, or token-accounting
stack is actually working. Run read-only; report findings, fix only on approval.

## Store inventory

Canonical Hermes paths (resolve `$HERMES_HOME`, never hardcode `~/.hermes`, when a profile is active):

| Store | Backs | Open it for |
|---|---|---|
| `state.db` | sessions, messages, FTS5 indexes | transcript growth, compression evidence, FTS health |
| `memories/MEMORY.md`, `USER.md` | the injected memory block | char-budget fill |
| `memory_store.db` | the fact store (`fact_store` tool) | trust scoring, entity resolution, duplicates |
| sessions/*.jsonl | gateway transcripts | on-disk retention |

Verify each path exists before concluding data is missing — a store living outside
`$HERMES_HOME` (e.g. under `~/`) will read as an absent file and manufacture a phantom finding.

`sqlite3` CLI may be absent — use the module, read-only:

```bash
python3 - <<'PY'
import sqlite3, os
c = sqlite3.connect('file:'+os.path.expanduser('~/.hermes/state.db')+'?mode=ro', uri=True)
q = lambda s,*a: c.execute(s,a).fetchall()
print('integrity', q('pragma integrity_check')[0][0])
for k in ('journal_mode','auto_vacuum','freelist_count','page_count'):
    print(k, q('pragma '+k)[0][0])
for t, in q("select name from sqlite_master where type='table'"):
    try: print(f'  {t:34}', q(f'select count(*) from [{t}]')[0][0])
    except Exception as e: print(f'  {t:34} ERR {e}')
PY
```

Timestamp columns in the fact store are `TIMESTAMP` holding **TEXT** (`'2026-09-06 13:30:48'`),
not epoch integers — a `strftime(..., 'unixepoch')` grouping returns NULL for every row and looks
like "no dates recorded". Group with `strftime('%Y-%m', created_at)`. Use `typeof(col)` before
concluding a value is NULL.

## Health checks worth running

- **Compression actually fires** — `select count(*) from messages where _compressed_summary=1`, grouped by `sessions.source`. Zero rows means the trigger path is dead, not that the conversation was short. `compacted` / `active=0` rows are pruning markers, not evidence of summarisation.
- **FTS is live and indexed** — time a `MATCH` for a common term; check orphan `rowid`s in `messages_fts` against `messages`. Verify the product's own sanitiser rather than hand-writing SQL: hand-written `MATCH` skips token quoting and throws on `-`, `.` and `"` in ordinary words, which mimics an injection bug that does not exist.
- **Degenerate distributions** — `count(distinct trust_score)`, `sum(retrieval_count)`, `sum(helpful_count)`. One distinct trust value or an all-zero counter means the scoring path has never executed, whatever the code says it does. A dead counter column (present in `CREATE TABLE`, only ever selected) is upstream-confirmed dead; any decay logic later built on it will read zeros.
- **Duplicate families** — group on `substr(lower(trim(content)),1,70)` to catch near-dupes that exact-match misses. Gateway envelopes, model-change notices and surface banners are the usual offenders; they are infrastructure noise, not remembered facts.
- **Provenance coverage** — count rows naming a source id (`content like '%msg\_%' escape '\'`, or a dedicated column). A store where only a few percent carry provenance cannot be traced back or corrected when wrong.
- **Truncation residue** — `count(*) where length(content)=N` for the extractor's cap. A spike at exactly N means content is being clipped before insert (see the silent-loss pitfall in SKILL.md). Also count colliding prefixes: `select count(*) from (select substr(content,1,70) k, count(*) n from facts group by k having n>1)`.
- **Referential integrity** — facts with no entity link, dangling join rows, orphan entities. Low entity coverage can make a whole retrieval action unreachable: a contradiction detector that skips facts with no entity row will return zero whenever most facts are unlinked, so report coverage as the finding rather than "the detector is broken".
- **Budget fill** — `len(file)` vs the configured `memory_char_limit` / `user_char_limit` **and** vs the compiled-in code default. Report both ratios; a file under a raised config limit can still exceed the default and fail writes the moment the config key is absent.
- **Token-accounting store** — check row count and mtime age. A healthy service serving `200` with an empty table and a multi-day-old mtime is reporting upstream numbers, not its own.

## Residual vs active leakage

After a fix lands, previously-written bad rows persist. To separate the two:

1. Group offending rows by creation month — long-dead months are residue; rows inside the current
   window mean something is still writing them.
2. Run the **current** extraction logic against the offending shapes (import the pattern table and
   test each shape directly). If the current regexes reject them, the leak is closed and the finding
   is "cleanup owed", not "still leaking".
3. Say which of the two you concluded, and why. Do not report historical residue as a live bug, and
   do not call a leak closed while rows from the current window remain.

## Reading a proxy claim

A `base_url` pointing at a local proxy is a claim, not a proof. Confirm in this order:

1. `ss -tnp` — established sockets from the agent process to the proxy port vs to the upstream provider.
2. The proxy's own counter (`/stats`, `/metrics`) — a lifetime request count attributable entirely to one *other* client means this client never used it.
3. `journalctl --user -u <unit> --since '30 days ago' | awk '{print $1}' | sort | uniq -c` — request days and whether traffic stopped on a specific date.

Header-based redirect schemes (`X-*-Base-Url` style) only take effect when a proxy actually receives the request. Sent to the upstream directly, they are inert. When they ARE consumed by the proxy they must keep naming the **real upstream** — that is correct, not stale.

A POST that hangs while the log shows only `ClientDisconnect` means the *client* gave up. Bisect by restarting the service with suspect env config cleared and re-POSTing against a known-healthy local upstream; if it still hangs, the fault is proxy-side. Cross-check the extension/plugin names in the service env against the installed binary — an extension name with no matching string in the binary is inert config that can still wedge the request path.

After changing routing, confirm the primary model is one the upstream actually serves (send its name through the proxy and read the error) and that no fallback leg points back at the proxy itself.

## Ranking findings

Order by blast radius on correctness, not by how easy the fix is:

1. Something documented as load-bearing that is not wired in at all — every downstream claim built on it is false.
2. A guard that admits more than intended (security/privacy), or a feature that has never executed.
3. Unbounded growth with no retention policy — quantify the daily rate and project a year.
4. Cosmetic staleness (expired lock rows, dead-PID build locks) — label as cosmetic and say why it is harmless.

Report same-card: wins and failures together. Quote the command and its real output for every claim; never assert a check that was not run.

## Two-pass shape

Pass 1 maps the subsystem and ranks defects. Pass 2 (a *fresh* audit) should re-run pass 1's
assertions first to prove the fixes held, then attack what pass 1 structurally could not: stored
**content** quality, consolidation/nudge wiring, budget ratios against both limits, and residual vs
active leakage. Re-run a saved assertion script rather than re-deriving probes; keep it assert-based
and exiting non-zero on any failure so it doubles as the regression gate.