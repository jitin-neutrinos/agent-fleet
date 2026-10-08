---
name: codebase-audit
description: "Use when Jitin asks for a read-only codebase audit."
version: 1.0.0
author: notjitin
license: MIT
platforms: [linux]
tags: [audit, review, report, read-only]
metadata:
  hermes:
    tags: [audit, review, report, read-only]
    related_skills: [hermes-plugins, capability-router-operations, astra-canvas]
---

# Codebase audit and report (the no-changes engagement)

Jitin's standing request shape: "review/audit/research X and present a report. Make no
changes to the codebase yet." The deliverable is a read-only findings report as ONE Astra
canvas card, ending with prioritized next steps and a direct question about which to do
first. Every fix waits for an explicit go.

## When to Use

Trigger on: "review and audit", "present a report", "research the codebase",
"make no changes to the codebase yet", "what is the current implementation". Skip when
Jitin asks for a fix or a build — that is implementation work, not this engagement.

## Procedure

1. **Route first**: `~/.tool-router/route --top N "<request>"`, load the named skills
   highest-score first; skip wrong-ecosystem picks with a one-line reason (e.g. an
   Elixir perf skill for a Python repo).
2. **Map structure**: when `<project>/graphify-out/` exists, `graphify query "<question>"`
   for architecture, dead code, god functions; raise `--budget` when output truncates.
3. **Gather evidence read-only**: `git status`/`log`/`diff` for commit state; `wc -l`/
   grep counts for size and health; timed runs ×3 for any latency claim; live service
   and config state for wiring claims; eval/log files for historical numbers — label
   those as not re-measured today.
4. **Cite per finding**: every findings-table row carries the command run or the measured
   number that backs it. Never mark a step verified that was not run.
5. **Prove "no changes"**: `git status` at the end must match the start. A stray modified
   file is a broken contract, not a footnote.

## Report card recipe (Astra canvas)

badges (read-only / findings count) → callout (the headline finding) → kpi row (headline
measured metrics) → findings table with `colTypes:["text","text","status"]` and a verdict
per row → callout danger for anything that needs the user's go → steps (P1/P2/P3, all
status todo, nothing done) → references (router card, graphify queries, sources).
Failures live in the SAME card as successes; never an all-green card while something
is broken.

## Discipline

- "Make no changes yet" bans file writes, config edits, service restarts, commits —
  including obvious fixes. Findings become the steps list; the fix is a separate go.
- Distinguish installed from firing (see the hermes-plugins proof ladder): files on disk
  and an enable-list entry prove nothing; a fresh timestamp on the per-message artifact
  against known live traffic is the evidence.
- When the audit uncovers a live defect (dead hook, dark guard), surface it as the headline
  and ask to fix before continuing — a broken thing outweighs the report. If Jitin says
  "fix it", the audit's findings list IS the scope: fix, verify end-to-end (real payload,
  real traffic), report what passed/failed/deferred in the same message.