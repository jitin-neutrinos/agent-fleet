# Astra training, ingestion & archive (sister project ~/Work/projects/astra-webui)

End-session review, chat auto-ingestion, the 14-day archive, and the training-dataset
builder. All server-side, zero-dep node.

## Archive (14-day retention) — reuse the gateway, never rebuild it
- The gateway owns session archival. Turn it on with `hermes config set sessions.auto_archive true`
  and `hermes config set sessions.auto_archive_days 14` (keys under `sessions:` in config.yaml).
- It is a SOFT-HIDE: sets the `archived` flag, recoverable, shown under the archived filter
  (`GET /api/sessions?archived=only|include`), never a delete. Pinned sessions are exempt. It sweeps
  from the gateway housekeeping tick AND from `hermes serve`'s session-list path
  (`_maybe_auto_archive_for_profile`) — so it runs even when only `hermes serve` is up.
- Do NOT write astra-side TTL/retention code. `sessions.retention_days` (default 90) is a SEPARATE
  hard-delete (`hermes sessions prune`) — a different feature; never conflate the two.
- The durable archive is the training DB (`data/astra-training.db`): every transcript lives there
  forever regardless of how a chat ended.

## End-session + auto-ingestion pipeline (`server/training.mjs`, `server/ingest.mjs`)
- ONE dump implementation, two callers: `dumpSession(sid, title, source, opts)` in `training.mjs` is
  shared by the end-session flow and the ingest sweeper. Never stand up a second transcript store.
- Ingestion is dump-equivalent: a transcript is "ingested" the moment it lands in `messages`;
  `sessions.ingested_at` records when (NULL = not ingested). No separate ingest state machine —
  dumping == ingesting, so the two can never drift.
- Sweeper runs on boot + every `INGEST_SWEEP_INTERVAL_MS` (default 15 min). It enumerates
  `GET /api/sessions?archived=include&min_messages=N`, SKIPS `is_active` rows (never snapshot a live
  chat mid-turn), and dumps the rest in batches. `POST /api/ingest/run` forces a sweep; an in-flight
  guard makes a concurrent call a no-op.
- Boot backfill: rows dumped before the `ingested_at` column existed are stamped on boot so the
  un-ingested count is honest.
- Fail-open everywhere: a gateway error degrades to a reported error, never a crash.
- Routes: `GET /api/ingest/status`, `POST /api/ingest/run`, `POST /api/training/dataset` (all authed;
  401 without a session cookie).

## Dataset builder (`buildTrainingDataset`) — each rule is a bug if broken
- user/assistant turns only; drop tool/system rows.
- trim to the FIRST user turn; require user-first AND assistant-last.
- collapse consecutive same-role turns into one (strict alternation) — never emit same-role adjacency.
- dedup by content hash.
- EXCLUDE internal pipeline sessions: the end-session reviewer runs as a `hermes chat --oneshot`
  session whose first user message is the review prompt (contains `PROMPT_TEMPLATE_VERSION:`). These
  are Astra's own machinery, never training data. (Without this, the reviewer's own transcripts leak
  into the fine-tuning set.)
- Output: one file per day `dataset-sft-<date>.jsonl` + a manifest reporting
  `conversations / skipped / internal_excluded`.

## Adding a check in astra-webui (do this every time you add server logic)
- Convention: assert-based `*.check.mjs` (bare Node, no test framework). `npm run check`
  (`scripts/run-checks.mjs`) AUTO-DISCOVERS every `*.check.*` file — no registration needed to run it.
- A new `*.check.*` file MUST get a row in the regression-gate manifest
  (`scripts/regression-gate.check.mjs`, shape `{id:"RG-0NN", found, symptom, guard:"scripts/x.check.mjs"}`)
  or the gate fails: "... is not in the regression manifest — add a row or it is unpinned."
- `npm run check` runs in PARALLEL and the regression-gate is flaky there (pre-existing; it re-runs
  server checks that bind fixed ports). Verify YOUR change with `node scripts/run-checks.mjs --serial`
  (reliable) and `node scripts/regression-gate.check.mjs` standalone (passes at every
  `ASTRA_CHECK_PORT_OFFSET`). Don't chase the parallel gate failure — confirm it is pre-existing by
  re-running with your check moved aside.

## E2E verification without touching live data
- Boot the server on a SCRATCH port + SCRATCH DB:
  `set -a; . ~/.config/astra-webui/env; set +a` (loads ASTRA_WEBUI_PASSWORD + ASTRA_HERMES_PASSWORD),
  then `ASTRA_WEBUI_PORT=3099 TRAINING_DB_PATH=<scratch>/t.db TRAINING_DATA_DIR=<scratch>/exports node server/server.mjs`.
  The env override is what guarantees the live DB is untouched — verify counts before/after.
- The background launch wraps node in a `bash -lic` parent. Killing only the node PID leaves the port
  held and the NEXT boot fails with EADDRINUSE (and silently serves the OLD code). Kill the process
  group / both PIDs, or confirm with `ss -ltnp | grep <port>` that the pid you think is serving is the
  one that owns the port.
- Auth flow: `POST /api/login {"password":...}` into a cookie jar, then hit routes with `-b <jar>`;
  an unauthenticated call must return 401.

## Deploy
- `systemctl --user restart astra-webui.service` (unit reads `%h/.config/astra-webui/env`).
- Health: `curl -s https://astra.jitinnair.com/api/health` → 200. Full flow + pitfalls live in the
  repo at `docs/training-pipeline.md`.
