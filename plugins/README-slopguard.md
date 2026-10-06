# slopguard enforcement plugins (2026-09-30)

Deterministic guards, ported from manpreet171/slopguard, installed on all four harnesses:
- Hermes: plugins/hermes/slopguard/ (register_hook pre_tool_call; enable via `hermes plugins enable slopguard`)
- Claude Code: hooks in ~/.claude/settings.json + ~/.claude/plugins/slopguard/ (upstream install)
- opencode: plugins/opencode/slopguard.ts -> ~/.config/opencode/plugins/ (loaded automatically)
- agy: plugins/agy/hooks/slopguard.py -> ~/.gemini/config/hooks/, hooks.json merged into
  ~/.gemini/config/hooks.json AND ~/.gemini/settings.json "BeforeTool"

Guards: secrets in file writes (.env exempt), nonexistent npm/PyPI packages before install.
Fail-open on network errors; blocks logged (Hermes: ~/.hermes/logs/slopguard.log).
