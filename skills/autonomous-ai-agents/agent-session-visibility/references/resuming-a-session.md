# Resuming a session you were handed the id for

The "continue from session `<id>`" shape. Distinct from the audit recipe below: the goal is
the current state plus the next step, not a findings report.

## Look up by primary key, not by search

```python
import sqlite3
db = sqlite3.connect('file:/home/notjitin/.hermes/state.db?mode=ro', uri=True)

meta = db.execute("""select id, source, title, started_at, ended_at,
                            message_count, tool_call_count, model, cwd
                       from sessions where id=?""", (sid,)).fetchone()
```

A `session_search` query built from your recollection of the topic can rank a *different*
session first and return nothing about the one you were handed. Discovery is ranked and
truncating; the PK lookup is exact. One `LIKE 'YYYYMMDD_HHMMSS%'` on `sessions.id` settles a
partial id too.

## The arc comes from user turns

```python
rows = db.execute("""select id, timestamp, coalesce(content,'') from messages
                     where session_id=? and role='user' order by timestamp""", (sid,)).fetchall()
for mid, ts, c in rows:
    print(f"--- {mid} ts={ts:.0f} len={len(c)} ---\n{c[:2500]}")
```

Every `user` row is a decision the user made. Read them in order and the session's shape is
visible: what was asked, what got redirected, what was steered mid-turn, what was asked last.
Truncate the echo of an `[ASYNC DELEGATION BATCH COMPLETE]` block — it is a system-carried
result, not a user instruction, and it dominates by length.

Filter the noise rows first:

- `[System: ...]` — model/provider switches.
- `[OUT-OF-BAND USER MESSAGE ...]` — a real steer, keep it, but it is the user talking mid-turn.
- Async-delegation batch blocks — subagent results, not user intent.

## The payload is the longest assistant message in the window

```python
w = [(mid, ts, c) for mid, ts, c in asst_rows if ts_user <= ts < ts_next_user]
top = sorted(w, key=lambda r: -len(r[2]))[:2]
```

Between two user turns the assistant emits a long payload (the answer, often a spec or a
fence) plus many one-line process notes ("found it:", "still invalid — let me read the
source"). The long one is the work product; the short ones are the trace. Reading every
assistant row wastes context and buries the payload.

Print the **largest** messages' full content, and the rest as role + tool name + length only.

## Watch for superseded answers

A long session can contain the same deliverable twice — an early framing that later work
replaced. The tell is that the later answer contradicts the earlier one on substance. Both
are in the same session; picking the wrong one is worse than either. Resolve it by checking
which one the **artifacts on disk** were built from:

```python
ls -lt <dir the session named>     # newest artifact wins
```

and by which answer sits latest in the turn sequence. State plainly in the reply when a
superseded version exists — the user usually does not remember producing it, and silently
picking one leaves them unsure whether their last question was answered.

## Verify the artifacts landed

```python
find ~ -maxdepth 5 -newermt "<session start date>" -name "*.pdf" | head -20
```

Session narratives say a report was delivered; files with mtimes inside the session's window
say whether it was. A claimed PDF that has no file on disk is a session that narrated rather
than shipped, and the reply must say so.
