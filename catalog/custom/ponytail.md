---
slug: ponytail
title: Ponytail
kind: plugin
summary: Behavior plugin that forces the laziest solution that actually works: YAGNI to stdlib-first ladder, root cause over symptom, one runnable check left behind.
repo: jitin-neutrinos/agent-fleet
install: claude plugin install ponytail@agent-fleet
attach: plugins/ponytail
---

# Ponytail

**Ponytail** is a behavior plugin for coding harnesses: it forces the laziest solution that actually
works. Climb the ladder — YAGNI → reuse in-repo → stdlib → platform native → existing dependency →
one line → minimum code. Fix root causes, not symptoms. Leave one runnable check behind.

## Modes

- `ponytail` — active reviewing lens while writing code
- `ponytail-review` — code review focused exclusively on over-engineering
- `ponytail-audit` — whole-repo audit for over-engineering
- `ponytail-gain` — measured impact scoreboard
- `ponytail-debt`, `ponytail-help` — debt harvest and quick reference

## Install

Claude Code (from this fleet's marketplace):

```bash
claude plugin install ponytail@agent-fleet
```

Hermes loads the same skill set from the store (`skills/autonomous-ai-agents/ponytail*`).
Installing the fleet store on any machine wires both.
