# Auditing a PLAN against the code and live services

For "review / audit / enhance the plan" requests where the artifact is a design or phase doc, not the code. Unlike the code audit, findings are fixed IN the plan doc and logged there; code, database and running services stay untouched.

## Procedure

0. Check whether an audit already ran (`git log -- docs/`, an audit-log table in the doc). A repeated request means a second pass on a DIFFERENT axis (first pass: doc vs repo; second: claims vs code and live probes) — repeating the same pass finds the same things.
1. Route once, load the named skills, then list every checkable claim in the plan: each named dependency, table, column, endpoint, role, config key, and each number a target rests on (latency, size, cost).
2. Verify each against its source of truth in ONE batched read-only call (independent probes in parallel):
   - dependencies: `grep <crate> Cargo.toml` (declared), the lockfile (already compiled), `cargo tree -i <crate>` (in the real build graph; a crate already present costs nothing to adopt);
   - schema: `\d <table>`, constraints (`pg_constraint`), grants, RLS flags;
   - callers: grep the symbol — zero callers means the interface can be redesigned freely;
   - validators and gates the plan assumes are strict: read the code, do not trust the name.
3. Size the plan's scale assumptions against real data (rows, lessons, orgs in the pilot). Cut heavy infrastructure (vector DB, framework) the data does not need and write a measurable deferral trigger instead.
4. Probe each live external dependency a target rests on, with the real credential, in one script: parse the key in-process, print timings and status, never the key. Record n and label results directional. If the target is unreachable on that backend, restate the target in the doc instead of keeping a promise the backend cannot keep.
5. Re-check every simplification against the plan's OWN guard laws. A lean shortcut can void a guard — loading a whole course into a tutor prompt leaked assessed lessons the integrity law forbids. Fix = a structural filter by the asking principal's entitlements at load time, plus a test asserting the forbidden text never appears in the assembled prompt.
6. Check ordering: a guard, flag or schema that a feature needs ships with or before that feature, never in a later phase.
7. Check cross-component effects: a new status code against the client's global handler (401 usually means log out), a new role string against deny-list checks, a new table against default privileges, a new migration number against the ones already planned.
8. Write the result into the plan: fix the sentence in place (no "UPDATE:" trailers); add one row per finding to an audit-log table (severity, finding, evidence = the command or number, fix); give every phase a runnable acceptance check; list deferrals with a decision trigger. Patch with a script that asserts each anchor exists before replacing (a missed anchor is otherwise a silent no-op), and anchor a new section on the NEXT heading instead of re-typing the section above it.
9. Commit the docs alone and leave `git status` clean. Report as one card: the finding that changed the plan most (including flaws in your own earlier draft), fixes with why, measured numbers, decisions you took on the owner's behalf, and the exact questions that need their go.
