# Verification harnesses — browser + load (committed, re-runnable)

Two harnesses live in the repo so every wave gets the same proof automatically.
Run them against a seeded QA org on private ports; never against the public hostname.

## Seed a QA org through the API (prerequisite for both)

Against the core (`BASE=http://127.0.0.1:5150` — the port the Next proxy bakes):

```
register → login (capture the orbit_session cookie)
→ POST /api/orgs → courses → modules → lessons
→ PUT /api/orgs/{slug}/lessons/{id}/uls (needs enough narration text or quiz-gen refuses with no_content)
→ POST /api/orgs/{slug}/courses/{id}/questions (mcq body: prompt, options[], answer, explanation)
```

The quizzes row can be inserted directly (`docker exec orbit-db psql … INSERT INTO quizzes …
slots = jsonb_build_array('<question-id>')` — slots is an array of question-id STRINGS, not
objects) when no provider key is configured; quiz-generation itself needs AI config.

**cargo test wipes the throwaway DB mid-suite** — re-seed after the final suite run, before
any smoke or harness run, or every login 401s.

## Browser harness — `scripts/browser-verify.cjs`

Playwright imported from `~/Work/projects/astra-webui/node_modules/playwright` (no install).
What it proves: login, course page, gradebook tab, quiz attempt start, answer, submit — in
BOTH themes, 390 px, asserting rendered content, the no-answer-leak key check, a pass
indicator, zero pageerror/console errors, no horizontal overflow.

Gotchas baked in (do not remove when editing):

- The login form is client-rendered behind Suspense — SSR HTML has no inputs, so
  `waitForSelector('input[type="email"]')` (20 s) before filling; `networkidle` alone times out.
- Core must listen on 5150: the script hits the core directly AND the browser goes through
  the Next proxy, whose `ORBIT_CORE_URL` default is 127.0.0.1:5150. A core on 5151 makes
  every proxied request 500 with ECONNREFUSED in the web log.
- The web server must be restarted after `next build` (see the stale-`next start` pitfall).
- Seed logging prints every status and the attempt id — a silent `ERR` there means the
  harness will 404 later, not that the app is broken.
- A fresh browser context per theme, and `waitForURL(/\/app/)` after login before
  navigating — without it every app page bounces to `/login?next=…` and the checks fail
  against the login screen.
- Node fetch cookie capture: push only `c.split(';')[0]` and replace same-name entries
  (latest wins) — a stale register-time session sent first 404s every later call while the
  hand-run of the identical request succeeds.
- psql `RETURNING` captured from stdout needs `.trim().split('\n')[0].trim()` — the command
  tag rides on line 2 and poisons the id.

## Load gate — `scripts/load/orbit.k6.js`

```
docker run --rm --network host \
  -e BASE=http://127.0.0.1:5150 -e EMAIL=… -e PASS=… -e SLUG=… \
  -e COURSE_ID=… -e LESSON_ID=… \
  -v "$PWD/scripts/load:/scripts" grafana/k6 run /scripts/orbit.k6.js
```

Core must run with `DB_MAX_CONNECTIONS=60` (the config default is 1 — 20 VUs exhaust it and
every request 500s with "Failed to acquire connection from pool", which reads like an app
outage).

Threshold design — three rules that keep the gate honest:

1. **Tag auth separately from the app SLO.** Argon2 login latency dominates any p95 that
   includes it; `tags: { type: 'auth' }` on the login call and threshold only
   `http_req_duration{type:non_ai}`.
2. **`http_req_failed` counts idempotent 409s as failures.** Enroll on replay returns 409
   "already enrolled" — the steady state. Threshold an explicit
   `Counter('unexpected_errors')` incremented on anything that is not 2xx/204 or an
   expected 409, and accept the 409 in the check.
3. **Fix script bugs before believing red thresholds.** The load user must ENROLL before
   progress (409 "Enroll in this course" otherwise), and enroll takes `{ email }` — an empty
   body 422s "Enter the learner's email". Both look like app failures under load.

Green shape at 20 VUs / ~100 s: checks 100 %, unexpected_errors 0, non-AI p(95) 25–70 ms.

## Route-gate check — `scripts/check_route_roles.py`

Every controller fn taking `auth::JWT` must call `open`/`require_role`/`require_platform_key`
or sit on an explicit allowlist; exits 1 otherwise and prints the route-to-roles matrix.
Probe it once with a fixture handler to confirm the exit code bites.
