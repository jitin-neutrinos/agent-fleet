# Moodle (and peer LMS) comparison — what to harvest from a mature LMS

Companion to the "audit X vs ours" procedure in SKILL.md. This file carries the *decisions*, so a
future session building gradebook / question bank / availability does not re-derive them.

## Verified scale markers (re-derive with the blobless-clone recipe if a newer version matters)

External reference point: moodle/moodle at one pinned SHA. ~67.6k tracked files, ~55.4k PHP files,
267 tables in `lib/db/install.xml` alone, ~450+ tables once plugins are counted (sampled 60 of 85
plugin `db/install.xml` files — true total is higher), 214 plugin directories across 12 families
(mod 23, enrol 13, auth 9, blocks 40, report 21, question/type 18, grade/report 7,
availability/condition 6, course/format 4, admin/tool 39, repository 21, filter 13), 1,523 Behat
features, 2,994 PHPUnit files, PHP >= 8.3 required, version line read from `public/version.php`.

Our side for the same comparison: core `wc -l` (Rust), web `wc -l` (TS/TSX), table count from
`core/src/models/_entities/`, endpoint count from the `.add("...")` lines across
`core/src/controllers/*.rs`.

## Borrow / rebuild / repurpose — the decision table

| Their artifact | Verdict | What we do |
|---|---|---|
| SCORM 2004 sequencing (`datamodels/sequencinglib.php` ~1.1k lines + `scorm_seq_*` tables) | Borrow the schema, not the code | Keep the non-sequencing scope cut; when a real multi-SCO package arrives, copy the rule/rollup *table shape* into `scorm_attempts` jsonb + derived columns |
| Question bank + quiz attempt model (9 quiz tables, 17 qtypes, qbehaviour, qformat) | Rebuild lean | One `qbank` table (question jsonb + difficulty + tag) + the slot/attempt/step shape; ship MCQ + short-answer + generated, skip the 17 qtypes and behaviours |
| Gradebook rollups (grade_items / grade_grades split, category weights, formula language, 6 reports) | Rebuild lean | Copy the item-definition-vs-earned-value split and the category tree with weights; skip custom formula language and grade history until a customer asks |
| Completion + availability conditions (date / grade / group / completion / profile) | Rebuild lean | Their 6 condition types are the right backlog; date + completion gating first, grade gating after gradebook |
| Cohorts vs groups | Rebuild lean | Cohort = site-wide cross-course, group = per-course; the split the multi-tenant v2.1 departments/teams/groups plan should mirror |
| Course backup/restore + IMS Common Cartridge | Borrow the format | CC import is the migration on-ramp from existing installs; ULS export stays the open-standard play — document the choice in `docs/SCORM_RESEARCH.md` |
| Events → observers → cron/adhoc task queue | Borrow the pattern | Formalise an events table + observer registry sized for our `core/src/tasks/` workers (they run 37 observers off this) |
| MUC (definitions + 5 pluggable cache stores) | Skip at pilot scale | One cache store covers us; revisit when the second app server lands — their own docs give the same trigger |
| Roles & capabilities runtime (context hierarchy + capability bitmasks, ~5k-line accesslib) | Skip — anti-pattern for us | Capability checks per context per request is their latency floor and a large attack surface; RLS + role enum + OrgScope guard does the same job at the DB boundary for free. This is our advantage, not a gap |
| PHP request-per-page bootstrap | Skip | A long-lived Axum process never pays it |
| Plugin-type explosion (~40 strongly-typed plugin types) | Borrow the ecosystem idea, not the mechanism | ULS-as-open-standard is our extension story; we want a stable course format others target, not 40 extension APIs |
| AI subsystem (provider plugins: anthropic/awsbedrock/azureai/deepseek/gemini/ollama/openai behind one manager; `aiactions` base with stored responses; placements) | Repurpose selectively | Confirms our one-gateway-trait design; their rate limiter (1h window, global + per-user, cache-backed) is worth copying verbatim — we have budget metering but no per-user rate cap |

## Do NOT copy (the traps)

- Capability-check-per-request permissions — biggest latency source and its own security surface.
- Fat core (their `moodlelib.php` alone is ~10k lines) — our core stays reviewable.
- Multi-tenancy by convention / admin discipline — never; RLS is the only version we ship.
- Portability tax of 6 DB drivers — Postgres-only is a deliberate saving.

## Performance comparison, honestly

- Report runtime-model differences (per-request bootstrap vs long-lived process) as architecture, not as a benchmark.
- A framework micro-benchmark (TechEmpower JSON endpoint, no DB, no LMS page) is only ever a throughput *ceiling* comparison; real page cost is DB-bound and per-user, which is why full-page caching is unsafe for authenticated LMS pages — say both halves in the same cell.
- Their own docs converge on the same advice: cache store + tuned worker pool + separate DB host, and never cache authenticated pages.

## Where these land in our backlog

Priority order that fell out of the comparison: qbank + grade_items split → events/observer registry →
per-user AI rate cap → sequencing table shape on first multi-SCO package → date/completion
availability conditions → ULS-export-vs-CC-import policy decision in `docs/SCORM_RESEARCH.md`.
