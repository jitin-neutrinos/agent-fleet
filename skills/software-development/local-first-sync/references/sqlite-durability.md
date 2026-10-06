# SQLite durability for a sole system of record

Depth for the storage-engine half: which pragmas, which bug class, and how to
prove the choice. Read before opening a new SQLite-backed log, or when a
retention job seems to do nothing.

## Assert the library version, not the runtime version

Runtimes bundle their own SQLite, so "the Node/Python version is new" says nothing
about the engine. Assert `sqlite_version()` in a check.

Known-bad range: SQLite **3.7.0 through 3.51.2** carries the WAL-reset race — a
checkpoint racing a WAL-resetting commit records frames as backfilled when they
were not, so a later checkpoint skips them and a committed transaction silently
evaporates. No error at write time, no error at checkpoint time. Fixed in 3.51.3.
Upstream also withdrew 3.52.0 days after release, so prefer 3.51.3+ or 3.53.0+.

**Newer runtime is not automatically newer engine.** A release channel can bundle
an older copy than what you already run. Test candidates and read the version back
before switching; the version-number instinct can walk you *into* the bug.

## Are you in the blast radius?

Preconditions: WAL mode, two or more connections on the same file in different
threads/processes, and a write colliding with a checkpoint. Check:

```sql
PRAGMA journal_mode;              -- 'wal'?
PRAGMA synchronous;               -- 1=NORMAL 2=FULL
```

Multi-process access is often documented in the repo's own comment ("the service
plus a detached runner"). What saves you is usually the *absence* of an independent
checkpointer: default auto-checkpoint runs on the committing connection, which is
safe by construction. **Never add a background `wal_checkpoint` thread or process
to a database in this state** — that is the single change that moves you from
"exposed but unlikely" to "in the blast radius". Record that prohibition in the
module.

## Pragmas that matter

| Pragma | Why |
|---|---|
| `journal_mode = WAL` | concurrent reader/writer |
| `synchronous = NORMAL` | in WAL this is still durable across **process** crash; only power-loss durability is traded. Right call for a recoverable log whose worst case is "re-pull the final message" |
| `auto_vacuum = INCREMENTAL` | lets purge return space. **Must precede table creation** — it cannot be changed once tables exist |
| `busy_timeout` | a multi-writer loser waits instead of throwing `SQLITE_BUSY` |
| `secure_delete = ON` | a plain DELETE leaves the text readable in freed pages |

`PRAGMA synchronous` is **per-connection**. Setting it on a second connection does
nothing to the writer, so a benchmark reports "no difference" because both runs
were identical. Apply it on the writing connection and read it back.

## Measure, then report honestly

Bench against the real writer, not a synthetic one. A per-row-autocommit figure
from research does not transfer to a batched writer — batching absorbs most of the
fsync cost, so the honest gain is usually a small multiple, not the headline
order of magnitude. If your measurement contradicts a prior claim, report both and
explain why they differ.

Assert on **stored row count**, not on a flush function's return value: a coalesce
timer may legitimately drain the buffer first, so a zero there means "already
flushed", not "nothing written".

## Retention mechanics

- `WITHOUT ROWID` tables have **no `rowid`**. `WHERE rowid IN (...)` silently
  matches nothing — retention becomes a no-op that still reports success. Cut on
  the primary key.
- Capture the purge boundary **before** the delete; afterwards the rows are gone
  and there is nothing left to compute a watermark from.
- Raise the watermark per key and **never lower it**, so a partial batch cannot
  make an earlier purge look undone.
- Batch-limit the work so a first run over a large backlog cannot monopolise the
  writer.
- Delete child rows with the parent, then assert no orphans remain.

## Prove durability under an unclean kill

`INSERT` + commit, then `SIGKILL` the process with no clean close, then reopen and
count rows. If the count is short, `synchronous` is too high for your tolerance.
This is the assertion that actually justifies the pragma choice.
