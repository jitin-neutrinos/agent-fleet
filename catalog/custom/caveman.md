---
slug: caveman
title: Caveman
kind: plugin
summary: Ultra-compressed communication mode: cuts output tokens to the bone while keeping every technical detail; filler dies, warnings never compress.
repo: jitin-neutrinos/agent-fleet
install: claude plugin install caveman@agent-fleet
attach: plugins/caveman
---

# Caveman

**Caveman** makes an agent speak in compressed, high-signal fragments: all the technical substance,
none of the filler. Great for long working sessions where you want outputs you can scan in seconds.

## Rules it enforces

- Terse compressed replies; drop greetings, restatements, filler.
- Keep every technical detail, number and caveat that matters.
- **Auto-clarity exceptions**: security warnings and irreversible-action confirmations are always
  written in plain, unambiguous English — never compressed.

## Install

```bash
claude plugin install caveman@agent-fleet
```

Ships from this fleet's marketplace; the Hermes skill set in the store carries the same rules.
