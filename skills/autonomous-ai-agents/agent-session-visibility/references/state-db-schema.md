# state.db schema notes — verified 2026-09-06 on kurama-core (Hermes 0.21.0)

Verified by direct inspection (`select name from sqlite_master where type='table'`) on the default profile. Counts at verification time: 58 sessions, 1,881 messages.

## Tables that matter

### sessions
Core columns: `id` (e.g. `20260906_203907_3fb944`; cron sessions `cron_<job>_<ts>`), `source` (cli/telegram/cron/kanban), `title`, `display_name`, `chat_id`, `last_activity_at` (epoch float), `message_count`, `tool_call_count`, `input_tokens`/`output_tokens`/`estimated_cost_usd`, `model`, `profile_name`, `parent_session_id` (session chains/continuations), `cwd`, `archived`, `pinned`, `hidden`, `tool_names`.

### messages
`id`, `session_id`, `role` (user/assistant/tool), `content`, `tool_name`, `tool_call_id`, `tool_calls`, `timestamp` (epoch float), `token_count`, `reasoning`/`reasoning_content`, `active`, `compacted`, `_compressed_summary`, `display_kind`.

### FTS
`messages_fts` (FTS5 over content/tool_name/tool_calls) + a trigram twin `messages_fts_trigram` — this is what `session_search` queries.

### hosted_rooms* (agent-to-agent layer)
~15 tables: `hosted_rooms` (members, authority gateway), `hosted_room_events` (seq-numbered event log), `hosted_room_links` (member→target transport), `hosted_room_remote_runs`, `hosted_room_policy_*`. All zero rows on this install as of verification — present but unused.

Other: `async_delegations` (delegate_task tracking), `session_model_usage` (per-model token/cost rollups), `delivery_obligations` (pending platform deliveries), `gateway_routing`.

## Worked queries

```python
import sqlite3, time
DB = '/home/notjitin/.hermes/state.db'
db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)

# Most recently active sessions (liveness = now - last_activity_at small)
for r in db.execute("""select id, source, title, last_activity_at, message_count
                       from sessions order by last_activity_at desc limit 10"""):
    age = int(time.time() - r[3])
    print(r[0], r[1], r[2], f'{age}s ago', f'{r[4]} msgs')

# Tail a live session's message stream
for r in db.execute("""select role, substr(replace(content, char(10), ' '), 1, 120), timestamp
                       from messages where session_id = ? order by id desc limit 6""",
                    ('20260906_203907_3fb944',)):
    print(r)
```

## Auditing a finished session by id

The ask "audit the work of session `<id>`" is answered from the DB, not from the session's own summary.
Read-only throughout; the deliverable is findings, never edits.

```python
import sqlite3, json, collections, datetime
DB = '/home/notjitin/.hermes/state.db'
db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
sid = 'YYYYMMDD_HHMMSS_xxxxxx'

meta = db.execute("""select id, source, title, model, started_at, ended_at,
                     message_count, tool_call_count, input_tokens, output_tokens,
                     cache_read_tokens, cwd, git_repo_root, cost_status
                      from sessions where id=?""", (sid,)).fetchone()

# tool-name histogram + role mix: the shape of the work before reading any of it
db.execute("select tool_name, count(*) from messages where session_id=?"
           " and tool_name is not null group by 1 order by 2 desc", (sid,))
```

`assistant` rows carry the INTENT (`content`) and, in `tool_calls`, the exact commands with their
arguments — join `tool_calls` back to the `tool` row via `tool_call_id` to see what each command actually
returned. That pairing is the audit: the claim lives in the assistant text, the evidence in the tool row.

**Re-run the verification, don't re-read the claim.** A session asserting "52 pass / 0 fail" or "fixed,
12/12" has told you what it believes; execute its own commands in the current tree and compare. This is
the only step that catches a gate shipped red, a stale baseline, or an assertion that cannot fail.

Then reconcile against the artifact, not the narrative:

- `git log`/`git reflog` for the session's window — did it commit, or leave everything untracked? Files on
  disk are not a delivery; check `git status --porcelain` and say so if the tree is dirty.
- `git archive HEAD | tar -x` into scratch + symlink `node_modules` to build what a CLONE would build. A
  working tree with untracked source passes locally and fails the clone.
- `find /tmp -newermt <session start>` to catch scratch writes into the wrong directory, and diff
  `git status` against a pre-audit snapshot so your own verification runs are disclosed too — running a
  suite often mutates tracked runtime state (ledgers, read-state) even when you changed no source.

Cost signals worth reporting: `cache_read_tokens` orders of magnitude above `input_tokens` means the run
re-imported module graphs from cold in many short subprocesses (fine on a free model, the real cost driver
under a paid one). `ended_at IS NULL` on a long-idle session means it never finalized — say that rather
than implying it exited cleanly.

- Default DB: `~/.hermes/state.db`
- Profiles: `~/.hermes/profiles/{ops,coder,reviewer,researcher}/state.db` (same schema)
- Prefer `session_search(profile='<name>', ...)` for these; fall back to direct read-only SQL.

## External agents (outside state.db)

- Running processes: `ps aux | grep -E 'claude|agy|opencode' | grep -v grep` — the full prompt is visible in the cmdline for `claude -p`.
- Claude Code transcripts: `~/.claude/projects/*.jsonl`.
- Established contract on this machine: scratch dir with `context.md` (in) + `findings.md` / output files + `claude-stdout.log` (out).
