# Runtime system prompt anatomy (observed render, 2026-09-06)

Order of sections in a ~12.7 KB render for the default profile:

1. **Hardcoded Nous persona rules** — reply-length matching, no filler, plain claims, "agree because it's right". Not editable.
2. **`---` separator, then SOUL.md** — the user's `## Identity: <host> desktop operator` block lands here, verbatim. This is the customization zone.
3. **Hermes self-reference** — pointer to https://hermes-agent.nousresearch.com/docs and instruction to load the `hermes-agent` skill before Hermes-related work.
4. **Mid-turn steering protocol** — spec of the `[OUT-OF-BAND USER MESSAGE ...]` marker and the rule to trust only that exact wrapper.
5. **Host/environment facts** — kernel, home dir, cwd, active profile, profile-isolation rule.
6. **Skills directive + catalog** — MUST-load rule, then `<available_skills>` tree (names + one-line descriptions only).
7. **Tool documentation + tool-use enforcement** — built by `agent/prompt_builder.py`; includes the mandatory-tool-use and verification blocks.
8. **Kanban task protocol** (when the gateway dispatches a board task).
9. **Memory + user profile dump** — contents of `memories/MEMORY.md` and `USER.md`, with char-budget headers.

## Where to intervene, per intent

| Intent | File |
|---|---|
| Blanket identity/behavior guardrails | `$HERMES_HOME/SOUL.md` (next session) |
| Role-specific rules for a specialist | `~/.hermes/profiles/<name>/SOUL.md` |
| Facts re-read every session | `memories/MEMORY.md`, `memories/USER.md` (budget-capped) |
| Hard enforcement (approvals, redaction) | `config.yaml` via `hermes config set`; hooks in `~/.hermes/hooks/` |
| Per-project rules | `.hermes.md` / `AGENTS.md` in the project (20 KB cap, injection-scanned) |
| Audit-only (do not edit) | `~/.hermes/hermes-agent/agent/system_prompt.py`, `agent/prompt_builder.py` |
