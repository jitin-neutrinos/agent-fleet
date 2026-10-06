---
slug: shell-hitl-gate
title: Shell HITL gate
kind: plugin
summary: Human-in-the-loop gate for Hermes terminal commands: coding profiles approve in bulk once per session, every other profile approves each distinct command.
attach: plugins/shell-hitl-gate
---

# Shell HITL gate

A Hermes plugin that gates every `terminal` / `execute_code` call through the human-approval prompt.

- Coding profiles (coder, reviewer) get **one bulk approval per session** — fast, still explicit.
- Every other profile is asked **per distinct command**.

Installed by the fleet store on any machine with Hermes (`plugins/hermes/shell-hitl-gate`). No
separate install step; re-running the store installer is the repair path.

```bash
curl -fsSL https://harness.jitinnair.com/install.sh | bash
```
