---
name: community-insights-dashboard
description: "Use for work in the community-insights-dashboard project."
---

# Community Insights Dashboard

AI Hub-native NLP analysis platform for the Neutrinos Discourse community (community.neutrinos.com). Location: `~/Work/Neutrinos/community-insights-dashboard/`. Plan of record: `implementation-plan.md` (v2) in the project root; MVP audit: `source/source-audit.md`; observability: `docs/observability-plan.md`.

## Architecture (as built)

- `app/` root. `docker-compose.yml`: db (pgvector/pg16 on 127.0.0.1:5433), backend (:8010 host / :8000 container), worker, frontend (:8081).
- `app/backend/` FastAPI: routes under `app/routes/`, services under `app/services/` (discourse incremental client, ingestion since-cursor, `aihub/` package with mandatory stub mode, aggregator, scheduler, jobs). Alembic in `backend/alembic/`. Tests in `backend/tests/` (93, stub mode, zero external calls).
- `app/worker/worker.py`: DB-backed job queue (ingest/analyze/assistant_cycle), `--once` drains, `--smoke` boots. Needs BOTH `DATABASE_URL` (asyncpg URL) and `BACKEND_PATH` env.
- `app/frontend/` React+Vite+Tailwind, GSAP (not Framer Motion), light theme, brand tokens in `src/brand/` + `src/theme.js`. Dev: `npm run dev -- --host 0.0.0.0 --port 5174`.

## Run commands

```bash
# backend (from app/backend)
DATABASE_URL='postgresql+asyncpg://insights:insights_local@localhost:5433/insights' .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
# worker one-shot (from app/ — cwd MUST be app/ so backend .env loads)
DATABASE_URL='postgresql+asyncpg://insights:insights_local@localhost:5433/insights' BACKEND_PATH=$PWD/backend backend/.venv/bin/python worker/worker.py --once
# tests
cd app && backend/.venv/bin/python -m pytest backend/tests -q
```

## Hard rules and pitfalls

- Port 8000 belongs to the neutrinos-mcp service — never bind it, never kill its listener. Backend uses 8010.
- pydantic-settings `env_file=".env"` resolves relative to CWD: the worker/uvicorn process must run from `app/` or the Discourse/AI Hub keys silently vanish (client falls back to keyless "public" mode — symptom: `stats.mode == "public"` in pipeline_runs.stats).
- `pipeline_runs.stats` column is NOT NULL — always insert `'{}'::jsonb` at run start.
- Discourse rate limits are aggressive (429 after a few rapid /t/{id}.json calls): the client has a global throttle (`_global_throttle`, min 0.25s between ANY two requests) — keep it, never bypass it, and pace backfills at ≥3s/topic. Full post backfill of 600 topics ≈ 30 min at that pace.
- Post bodies can have NULL/empty text; timestamps from Discourse arrive as ISO strings — `parse_dt()` them before insert (asyncpg rejects strings for timestamptz).
- Stub mode (`AIHUB_TOKEN_*` unset) is the default: results stamped `model_version="stub-1"` (keyword heuristics). Real AI Hub tokens flip it over with zero code changes.
- Frontend: all colors via `src/theme.js` from brand tokens; GSAP only (Framer Motion removed); dev proxy target set via `VITE_PROXY_TARGET` env (default :8000 is WRONG for local runs — use 8010).
- Frontend data normalizers live in `src/api.js` — backend objects (e.g. `pipeline_health` = {ingest:{...},analyze:{...}}) must be flattened to display scalars THERE, never rendered raw (React crashes on object children).

## AI Hub (Sandbox first)

- Tokens page: per-model tokens, expiry Never for pipeline use. Deployments page: deployment ids per environment. Assistant: id + knowledge-source ids.
- **Dataset audit procedure** (run before any upload/retrain): parse every CSV row with the stdlib `csv` module and verify programmatically — column-count consistency, label enums (priority `high/medium/low`, sentiment `pos/neu/neg`, NER `PERSON/PRODUCT/EMAIL`), class distribution, duplicate/conflicting-label counts, UTF-8 no BOM, and for NER that every span slice equals its text and spans don't overlap. A passed parse is the only proof of usability — never eyeball.
- **Fix upload settings, not just files**: tick "Discard the First Row" (all files have headers); leave Advanced Configuration cleaning OFF for extraction models — cleaning mutates the text so the stored char offsets point at the wrong words (silent annotation corruption). Advanced config is safe on prediction models.
- An in-UI lock file (`.~lock.<name>.csv#` next to the export) means the file is open in LibreOffice — close it before upload or a stale copy gets uploaded.
- The extraction wizard requires 25+ manually tagged examples IN THE UI before Start Training appears; pre-annotated CSVs do not satisfy this. Budget 20–30 min.

### Priority model accuracy (observed: high recall = 0, medium ≈ 84%)

- With high at 4.5% of rows the classifier learns "never predict high" — recall 0 on the minority class is the expected collapse, not a platform bug. Medium learning fine (84%) while high fails confirms the frequency threshold, not tooling, is the cause.
- Improvement sequence, in order: (1) re-scrub labels against a one-paragraph "what counts as high" rubric — heterogeneous highs (release notes, vulnerability reports, guides, incidents) dilute the concept; decide if announcements belong in high at all; (2) add/oversample REAL high examples toward ~20% of corpus; (3) retrain via **Retrain → Add New Data** (same model, new version — no re-setup); (4) batch-test on a ground-truth file of REAL posts only; (5) iterate via Review Hub corrections.
- Synthetic augmentation works when seeded and modest: variants derived from real minority examples (light rewrites, prefix jitter, truncation, templates filled with real product names/versions), ~3–4 variants per real row, never from scratch — naïve generation underperforms seed-guided per 2025-26 literature. **The batch-test CSV must contain zero synthetic rows** — synthetic ground truth turns the F1 gate into a memorization check.
- Training data: `app/scripts/export_training.py` → `app/exports/training_{priority,sentiment}.csv` (text + label columns; AI Hub Text Prediction models, category column select at upload).
- NER in AI Hub = **Extraction → Text tab** ("Text Extraction Model"), not Classification. Upload CSV/Excel with a `text` column + a `ground_truth` column holding JSON: `{"LABEL": [{"label": "LABEL", "start": N, "end": N}]}` (char offsets into text). Build recipe + verification gate: `references/ner-dataset.md`; artifacts: `app/exports/training_ner.csv` (upload) and `training_ner_flat.csv` (human-review copy).
- Knowledge Source (assistant) accepts ONLY Excel, Word/PDF documents, or a webpage URL — never CSV. Convert CSV to xlsx before upload.
- `/api/insights/ingest` is the Assistant write-back gate: X-Ingest-Token header, evidence post ids validated, invalid → 422.

## Go-live checklist (AI Hub model training & deployment)

Work through the steps in order. AI Hub will not let you run a Batch/Single test or create a token against an undeployed model — **deploy right after training, before you validate or make tokens.**

### Step 1 — Train the three models

Training data is already exported and waiting in `app/exports/`:

| File | Model | AI Hub type |
|------|-------|-------------|
| `training_priority.csv` | Priority classifier | Prediction → Text |
| `training_sentiment.csv` | Sentiment classifier | Prediction → Text |
| `training_ner_v2.csv` (see `NER_v2_README.md`) | Entity extraction | Extraction → Text |

For each: **Prediction** (or **Extraction**) → **Text** tab → **Add** → upload the CSV → pick the text column and the label column → name the model.

While still in the creation wizard, you'll hit a step called **"Define the rules"** — this is the Review Hub feedback-loop rule, set here, not later. Pick one of:
- **Always** — every prediction goes to your Review Hub queue.
- **Never** — nothing goes to Review Hub.
- **Confident** — only predictions below a confidence threshold you set (0.75 is a sensible start) go to Review Hub. **This is the one we want.**

For the **NER extraction model only**, this rule is set **per entity** (PERSON / PRODUCT / EMAIL each get their own Always/Never/Confident choice) — set all three to Confident/0.75 unless you want different thresholds per entity type.

⚠️ **Extraction (NER) needs manual tagging before it will train** — Prediction does not. After the rules step, the platform shows you the uploaded text on the left and your three entity identifiers (PERSON/PRODUCT/EMAIL) on the right. Click an identifier, then click the matching text on the left to tag it — repeat for **at least 25 tagged examples** across the file. The **Start Training** button only appears once you hit 25. This is manual, one-by-one work; budget 20–30 minutes for it.

⚠️ **The exact label strings matter.** The backend maps AI Hub's returned category name onto our enum. Right now it accepts `high` / `medium` / `med` / `low` / `p1` / `p2` / `p3` for priority, and `pos` / `positive` / `neu` / `neutral` / `neg` / `negative` for sentiment. If you train with anything else ("High Priority", "Critical", "😀"), tell the maintainer the exact strings and they will extend the mapping — otherwise every prediction is rejected with a clear error rather than silently mis-filed.

### Step 2 — Deploy each model

Do this *before* validating or making tokens — both of the next two steps require it.

Deployment → pick **Sandbox** → **Add** → name it, paste the license key (contact `subscription@neutrinos.com` if you don't have one) → **Submit**. Then, on each model's version page, kebab menu (⋮) → select **Sandbox** → enable **Deploy to Sandbox** → pick the deployment unit you just made → **Submit**.

### Step 3 — Validate each model

Now that it's deployed: on the model version page, left panel → **Test** → **Batch** tab → **Add** → select the Sandbox environment → upload a CSV that includes a **Ground Truth** column (a sample template is downloadable there) → **Start Testing**.

The plan's gate is **≥90% F1 on the High class** before priority scores are shown to leadership without a "provisional" label. Send the Accuracy/Precision/Recall/F1 numbers to the maintainer and they will record them on the `model_versions` row.

### Step 4 — Day-to-day: the Review Hub queue

This is the accuracy loop, running on the "Confident" rule you set in Step 1. Your ~15 min/day is: **Review Hub → Pending →** Confirm / Skip / Ignore. The backend polls the results it stored and pulls your verdicts back into `review_feedback` automatically; corrections also update the local prediction.

### Step 5 — Create the Analyst assistant

Follow the assistant setup documentation for the directive text and guardrails.

Two things that differ from that document now:
- **Do not** plan on a knowledge source holding the rolling analysis data. The API is read-only for knowledge sources, so the nightly cycle sends the current analysis extract inline in the message instead. Map knowledge sources only for static reference material (product glossary, module list) — the maintainer auto-discovers whatever is mapped (`assistant/knowledge/find-all`).
- **Do not** configure the API Connector yet. It needs AI Hub to reach this machine, which it cannot while running on localhost. The nightly cycle pulls the insights instead and runs them through the identical validation gate. The connector switches on when the stack is hosted.

In the assistant's **Instruction** panel, set **Output format** to **JSON** (default is Raw text) and define the JSON schema there, then deploy the assistant the same way as Step 2.

### Step 6 — Create four tokens

**Tokens → Sandbox → Add.** One per *deployed* model, **Expiry: Never** (the pipeline is unattended; 30 min / 3 h tokens will break it overnight).

| Token | Training Type | Data Type | Model |
|-------|---------------|-----------|-------|
| NER | Extraction | Text | your extraction model + version |
| Priority | Prediction | Text | your priority model + version |
| Sentiment | Prediction | Text | your sentiment model + version |
| Assistant | Assistant | — | Community Insights Analyst + version |

**The token value is shown once.** Copy it before clicking OK.

### Step 7 — Copy two cURLs

On the **Integrations** page of *one* Prediction model and *one* Extraction model, select your version + Sandbox + the **Predict Text** / single-test API and copy the cURL.

This is the one thing the maintainer cannot verify from the docs alone: whether your trained models take `{"text": "..."}` or `{"input": "<column name>: "..."}`, and whether your sandbox uses exactly the documented paths. Paste both cURLs (with token redacted) to the maintainer and they will confirm or adjust in one line of config.

### What to send the maintainer

```
1. Priority label strings (exact):        ______ / ______ / ______
2. Sentiment label strings (exact):       ______ / ______ / ______
3. Batch validation metrics per model:    accuracy / precision / recall / F1
4. AIHUB_TOKEN_PRIORITY=
5. AIHUB_TOKEN_SENTIMENT=
6. AIHUB_TOKEN_NER=
7. AIHUB_ASSISTANT_TOKEN=
8. AIHUB_BASE_URL=                        (confirm https://aihub-staging.neutrinos.com)
9. The two cURLs from Step 7 (token redacted)
10. Optional, for traceability only:
    AIHUB_PRIORITY_DEPLOYMENT_ID=
    AIHUB_SENTIMENT_DEPLOYMENT_ID=
    AIHUB_NER_DEPLOYMENT_ID=
    AIHUB_ASSISTANT_ID=
```

Put the tokens straight into `app/.env` rather than pasting them in chat if you prefer — just tell the maintainer they are in and they will read the file. `app/.env` is gitignored, and the repo is not a git repository yet.

### Decision A — Discourse backfill: DONE, in progress

Cursor was cleared and the full backfill is running now (job `ingest`, queued as `job_queue` id 51). It walks every reachable topic from `/latest.json` (~1250 of the forum's 1271 — the ~21 gap is category-definition topics Discourse itself excludes from listings) and every post in each, throttled and `Retry-After`-aware. The maintainer will report the final topic/post counts against the forum's ground truth (`topics_count=1271`, `posts_count=6191` from `/about.json`) once it finishes.

### Decision B still needed from you

**Analyse the whole corpus on day one, or only new posts?**

2082+ posts × 3 models ≈ 6,250+ AI Hub calls for a full re-analysis with real models (more once the backfill lands the rest of the forum). At `AIHUB_CONCURRENCY=4` that is roughly 15–30+ minutes and, more importantly, whatever your sandbox quota charges for it.

Options:
- **New posts only** (default): existing stub results stay, real models apply going forward. Cheapest, but the dashboard mixes `stub-1` and real results.
- **Full re-analysis**: the maintainer clears the analysis markers and everything is re-processed once with the real models. Clean data, one bounded cost.

### After you send the values

The maintainer will:
1. Put the tokens in `app/.env` and restart the two services.
2. Run one post through each model end to end and show the raw AI Hub response next to the row it produced — so we confirm the contract on real traffic before turning the scheduler loose.
3. Record each model version and its Step-3 metrics in `model_versions`.
4. Run whichever re-analysis you chose in Decision B.
5. Trigger one assistant cycle and show the insights it produced, the ones the evidence gate rejected, and why.

### Still open, not blocking you

- `Admin.jsx` is styled with Tailwind colour classes that do not exist in the brand theme (`bg-surface`, `text-primary`, …), so the page renders close to invisible, and it is dark-themed against the light-only brand rule. Needs a rewrite in the brand system — say when.
- No retention job (`§5`: "raw analysis rows kept 18 months").
- 23 one-shot `patch_*.py` scripts in the repo root, and `video.mp4` (7.3 GB). Safe to delete — the maintainer has not touched them.
- The repo is still not a git repository.

## UI decisions (locked by user)

- Layout = sidebar + page content ONLY: no header band, no footer. Mobile keeps a slim
  nav-toggle bar (lg:hidden).
- Logo lives at the top of the sidebar (white horizontal, 54px tall, hard-left aligned
  via `-mx-2 pl-0` — the user rejected centered/margin-aligned versions repeatedly).
- Clicking the logo collapses/expands the sidebar, Claude-style: GSAP timeline 240px↔68px,
  labels fade out first, icons re-center (`w-10 justify-center`), content margin tweens
  in sync (`#content-shell` padding), 0.45s power3.inOut. Collapsed = icons only; pill
  still tracks the active item. Reduced motion snaps.
- Frontend normalizers in `src/api.js` must flatten backend objects (e.g.
  `pipeline_health = {ingest:{...},analyze:{...}}`) to scalars before render — React
  crashes on object children.

## Delegation lessons (GLM 5.3 via OpenCode)

- Use `opencode run --auto` for headless build agents — without it, permission-gated
  commands auto-reject and the agent dies on its first `find` (symptom: "user rejected
  permission" on a headless run).
- Give agents a task file (`specs/task-*.md`) rather than a long inline prompt, and
  end every task on a machine-checkable gate (pytest green / build passing). Always
  re-run the gate yourself; agent self-reports are not verification.
- The default "Sisyphus" agent crashed on launch while `--agent build` worked — when
  OpenCode crashes agent-specifically, try the plain build agent before debugging deep.
- OpenCode 1.18.x: tool-router plugin injected a synthetic part with id prefix `tr_`
  which the schema rejects (expect `prt_`) — instant ~2s crash on every non-trivial
  prompt while trivial ones pass (masks the bug). Fix lives in the plugin file.

## Ops notes

- Local phase: no auth, bind 127.0.0.1. Go-live: Azure AD SSO, roles leadership/pe (pe = admin with read-only SQL access enforced at the DB role level).
- Logs: 5-day retention plan (Loki 120h + rotated JSONL) per docs/observability-plan.md — WP7, not yet built.
- Frontend visual verification: playwright MCP + `browser_navigate` to localhost:5174; check computed geometry with `browser_evaluate` (getBoundingClientRect), not pixel sampling. Playwright MCP needs chrome at /opt/google/chrome/chrome (symlinked to ~/.cache/ms-playwright chromium).
- If vision_analyze returns provider 429/余额不足, fall back to DOM-geometry checks or PIL pixel sampling — do not block on it.

## Community Admin bot (sibling project, ~/Work/Neutrinos/community-admin-bot/)
- Build spec of record: `~/Work/Neutrinos/ai-hub/community-admin-assistant-spec.md` (directive with XML-tagged sections + @Neutrinos Docs MCP tool catalog + [ESCALATION] marker contract, guardrail settings, rollout order). No-omissions protocol: `~/Work/Neutrinos/ai-hub/no-omissions-protocol.md`.
- Icon: `~/Work/Neutrinos/ai-hub/assets/community-admin-icon/community-admin-icon.png` (+ `-trim` variant); midnight/white/celeste per brand-core iconography rules (never reproduce the actual Neutrinos symbol in generated art).
- Assistant token lives in `community-admin-bot/.env` (0600) as AIHUB_TOKEN / AIHUB_BASE_URL / AIHUB_ENV=sandbox; same values feed the planned escalation middleware and the Insights stack if they share the sandbox tenant.