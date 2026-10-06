# Training pipeline: chat ingestion, archive, dataset hygiene

Lives in `~/Work/projects/astra-webui`: `server/training.mjs` (end-session
pipeline + shared dump), `server/ingest.mjs` (auto-ingest sweeper + stats),
`server/dataset.mjs` (SFT hygiene builder).

## The 14-day archive is the gateway's own switch — do not rebuild it

`~/.hermes/config.yaml` → `sessions.auto_archive: true` +
`sessions.auto_archive_days: 14`. Soft-hide, **never delete**, pinned sessions
exempt. It sweeps from the gateway's housekeeping tick AND from `hermes serve`'s
session-list path. Set the key; do not write a parallel retention tier in astra —
two archive systems can only drift. The separate hard-delete is
`sessions.retention_days` (default 90); do not confuse the two when the user says
"archive".

## Ingestion is dump-equivalent — never build a second state machine

A transcript is "ingested" the moment it lands in the `messages` table (via the
end-session button OR the auto-ingest sweeper). `sessions.ingested_at` records
when. Dumping == ingesting, so the two can never disagree.

- Sweeper (`server/ingest.mjs`): on boot + every `INGEST_SWEEP_INTERVAL_MS`
  (default 15 min). Lists `GET /api/sessions?archived=include&min_messages=N`,
  **skips `is_active`** (never snapshot a live chat), dumps the rest in batches.
- `POST /api/ingest/run` forces a sweep; an in-flight guard makes it a no-op
  while one runs.
- Backfill pre-existing rows on boot, or every already-dumped session reads as
  un-ingested forever.

## The archive is agent telemetry, not chat — always hygienize before training

Measured on the live archive: **94% of all text is tool output** (42.7k rows /
113 MB of JSON envelopes), 28.7k assistant rows carry no prose at all (they are
pure tool calls), and 209 sessions are automation. A naive export teaches the
model JSON escaping and noise.

| Rule | Effect |
|---|---|
| Drop `role='tool'` rows | the result body never enters the dataset |
| Keep ONE compact heading per tool call | `terminal: grep -rn login` — the trace of what happened survives, the payload does not |
| Unwrap JSON envelopes | `{"output":…}` / `{"content":…}` → their text; a bare call envelope → `""` |
| Exclude automation sources | `cron` / `oneshot` / `tool` / `unknown` are machinery, not conversation |
| Exclude internal pipeline sessions | the end-session reviewer runs as a `hermes chat --oneshot` session whose first user message is the review prompt (`PROMPT_TEMPLATE_VERSION:`) |
| Strip harness scaffolding | `[System: …]`, `[System note: …]`, `[Surface: …]`, `[IMPORTANT: … background process …]`, `[Background process … heartbeat]`, `[OUT-OF-BAND USER MESSAGE …]`, `[STILL IN PROGRESS]`, `[CONTEXT COMPACTION]`, `REFERENCE ONLY` |
| Drop boilerplate | the greeting prompt, "request was not processed", interrupted/stopped replies |
| Merge same-role neighbours, then render/truncate ONCE | truncating before merging lets a merged turn exceed the cap |
| Truncate oversized turns | user ≤8k, assistant ≤6k, total ≤24k chars; mark `[…truncated]` |
| Dedup by content hash | of the final conversation |

Result on the live archive: 105.2 MB → 3.8 MB (96.4% reduction), 543
conversations, 2,646 turns, avg 4.9 turns. Knobs:
`DATASET_MAX_USER_CHARS`, `DATASET_MAX_ASSISTANT_CHARS`,
`DATASET_MAX_TOTAL_CHARS`, `DATASET_MIN_USER_TURNS`.

Order matters in the filter chain: check the **marker** before the **source** if
a fixture is meant to prove one of them — a `oneshot` source hits the automation
filter first and the internal-marker branch never runs.

## Measure the output; do not eyeball a sample

Ship a QA pass that counts the failure classes on the built file: bad boundaries
(first ≠ user, last ≠ assistant), same-role adjacencies, oversized turns,
scaffolding residuals, boilerplate residuals. Zero across all five is the bar.
The first sample record looked fine while 23 reviewer sessions were still
leaking into the set — a sample is not verification, a count is.

## Check-harness conventions in this repo

- Checks are `*.check.mjs|ts`, assert-based, no framework, run under bare node.
- `scripts/run-checks.mjs` auto-discovers them. A new check **must** be added to
the `REGRESSIONS` manifest in `scripts/regression-gate.check.mjs` (id `RG-nnn`,
symptom, guard path) or the gate fails with "is not in the regression manifest".
- The runner prints only the **last line** of a failed check. When the gate fails
  inside the runner but passes standalone, run the check directly to see the real
  message.
- Diagnose with `--serial`. The parallel runner has a long-standing flake where
  the regression gate reports a failure the check does not reproduce alone.
  Confirm a failure is yours by removing your check and re-running: if it fails
  identically, it is pre-existing — say so instead of chasing it.
- Fixtures must actually reach the branch under test. A `MIN_MESSAGES` filter
  silently dropped the fixture meant to exercise the "no user turn" branch, so
  that path was never covered while the check reported green.

## e2e against the live gateway without touching live data

Boot the server on a scratch port with `TRAINING_DB_PATH` and
`TRAINING_DATA_DIR` pointed at scratch. Log in with `POST /api/login` using
`ASTRA_WEBUI_PASSWORD` from `~/.config/astra-webui/env`, keep the cookie jar,
then hit the routes. Confirm the live DB row counts are unchanged afterwards.

**Verify the port is owned by the NEW pid before trusting any result.** Killing
the parent bash PID leaves the node child holding the port; the new server then
fails to bind silently and the OLD server answers — a stale build looks current
and you debug the wrong code. `ss -ltnp | grep <port>`.

Deploy with `systemctl --user restart astra-webui.service`, then confirm
`https://astra.jitinnair.com/api/health` → 200.

## Review page: list rows by what they ARE

The "Ended sessions" list carries EVERY archived transcript (800+), most of them
auto-ingested with no review ever run. Rendering them all reads as "a lot of
items in review" while the counters above say 0 in flight — a display bug, not a
stuck queue. Split by `job_status`: `null` → Ingested, non-`done` → In review,
`done` → Closed. A list that does not match its own tiles is the bug.

## The reviewer session runs gated — plan the review around search/read only

The end-session reviewer runs as a single-query `hermes chat --oneshot`, and in single-query mode
no user is present to approve flagged tools. Proven on 20261004_170152_cc0ce3 (the reviewer for
session 20261003_184420_b51165): `terminal` came back gated early, then `execute_code` was
BLOCKED with `Tool 'execute_code' requires approval (Profile 'default' wants to run a shell
command: …) but single-query mode (-q) runs without a user present to approve it`. The approval
gate says the unlock is `approvals.single_query_mode: approve` in config.yaml — but the review
never needed it, because ripgrep-backed search and paged reads cover the whole job.
Re-confirmed 2026-10-05 reviewing 20261004_170204_93a8db: `execute_code` was blocked
again, this time with a *different* message (`BLOCKED: execute_code runs arbitrary local
Python … Single-query mode (-q) runs without a user present to approve it`). The block text
varies by harness version, so match on `execute_code` + `single-query` rather than on an
exact string, and treat the search/read-only path as the plan from the start — do not spend
a call discovering the block.

- **Structure first, by counts.** `search_files` count/content mode over the transcript:
  `^\[user\] ` for the asks (with line numbers), `^<tool_calls>` for turn volume, exact-sentence
  counts to size a degenerate loop (in b51165: 629× "I'm going in circles" + 632× "Let me check
  the vault first"), and a commit inventory straight from stored tool-result JSON
  (`"output": "[main 9543f31] feat…"` / `"output": "<sha> fix…"`, ~15 `"output": "[main "` rows).
- **Then targeted windows, not full re-reads.** `read_file` ~8-12-line windows after each
  `[user]` marker recovers the real ask, and the last ~150 lines carry the EOF state; paged
  content searches (offset until the `{"total_count": N}` JSON result appears) bound anything
  longer. Windowed reads at a fixed line stride with identical byte counts prove a region is
  verbatim-repeated and skippable.
- **Compaction is near-certain on a multi-MB transcript and consumes read content.** The
  checkpoint kept only byte counts for the big read windows (the transcript's own compaction
  summary says so: re-read ranges instead of trusting it for quotes). Timeline that worked: the
  full file was read breadth-first, compaction hit at ~line 9175, and the rest of the run was
  search-driven re-derivation (user-marker windows + commit searches) rather than linear re-reads.
- **Before writing any doc update, read the skill's references first.** That pass found the
  reviewed session's core lessons (provider persistence, composer measurement, blob guard, build
  verification) already captured in `references/config-page-patterns.md` + SKILL.md — whole
  duplicate write avoided. The only genuinely missing lessons were the reviewer-environment
  facts above and the fourth loop shape; see SKILL.md "Pitfalls".
- **`search_files` with `file_glob="**/..."` returns `total_count: 0` and no error** — the glob
  is matched against the file basename, never a path segment (proven 2026-10-05 on the reviewer
  for 20261004_103900_c3d723: `**/SKILL.md` → 0 hits, `SKILL.md` → 2 hits, same pattern). On a
  reviewer run this is worse than a miss: it reads as "no skill documents that lesson", which
  invites a duplicate write into the wrong file. Use a bare basename glob and narrow with
  `path=`. Full rule table: `using-superpowers/references/hermes-tools.md`.
  **Root cause, and why this reviewer shape hits it every time:** `docInventory()` in
  `server/training.mjs` is a NON-recursive `readdirSync`, so the prompt's inventory lists only
  depth-1 directories (`dev`, `projects`, …) and never the skill that owns a lesson
  (`dev/strangler-fig-rust-port`, `projects/astra-webui/references/…`). Skill ownership is
  discoverable ONLY by content search, and the natural first search is exactly the glob that
  scores 0 — the prompt pushes the reviewer straight at the failing form.
- **A reviewer session that reviews another reviewer session is still worth a real edit** — do
  not assume "meta" means "nothing durable". Reviewing 20261004_103900_c3d723, the previous
  reviewer had correctly reasoned its way to one line (the `execute_code` kernel-cwd trap in
  `strangler-fig-rust-port`) and patched it; that edit is verifiable at SKILL.md:179-184, so the
  only surviving delta was a search trap the reviewer itself had hit. The generalisable lesson is
  the reviewer's own method: read the target skill's full text before writing, then keep only
  what is provably missing. Six of that session's seven candidate lessons were already in the
  skill — an unverified restatement is still a duplicate write.
- **Check for an existing per-sid reviewer note before re-deriving anything.**
  `docs/training-pipeline-*-reviewer-note*.md` encodes the reviewed sid in the
  filename (`-93a8db`, `-5e999a`, `-547b29`, `-cc0ce3`; the undated base note is
  `20261004_092404_a69306` per its H1). Proven 2026-10-05 on the review of
  `20261004_170204_93a8db`: the note already existed and named that session's
  one surviving delta, so the transcript read was skipped entirely. Lookup
  first; the read is the expensive part, not the decision.
