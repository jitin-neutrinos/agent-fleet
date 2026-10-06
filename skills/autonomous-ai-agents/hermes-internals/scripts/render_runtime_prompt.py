#!/usr/bin/env python3
"""Render the actual Hermes runtime system prompt to a text file.

Usage: python3 render_runtime_prompt.py [SOUL.md path] [output path]
Defaults: $HERMES_HOME/SOUL.md, ./runtime_system_prompt.txt

Validated against hermes-agent source 2026-09-06 (agent/system_prompt.py).
If build_system_prompt grows new agent-attribute requirements, the
AttributeError traceback names the missing attribute — extend the stub.
"""
import sys, os

HERMES_SRC = os.path.expanduser("~/.hermes/hermes-agent")
sys.path.insert(0, HERMES_SRC)

from agent.system_prompt import build_system_prompt  # noqa: E402

soul_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    os.environ.get("HERMES_HOME", "~/.hermes") + "/SOUL.md")
out_path = sys.argv[2] if len(sys.argv) > 2 else "runtime_system_prompt.txt"

class FakeAgent:
    def load_soul_identity(self):
        with open(soul_path) as f:
            return f.read()
    valid_tool_names = {"skill_view", "terminal", "read_file", "write_file",
                        "web_search", "web_extract"}
    _tool_use_enforcement = "auto"
    def __getattr__(self, name):
        if name.startswith("_"):
            if name.endswith(("text", "prompt")):
                return ""
            if "plugin" in name or "section" in name:
                return []
            return False
        if "plugin" in name or "section" in name:
            return []
        if "text" in name or "prompt" in name:
            return ""
        return [] if not name.startswith(("is_", "has_", "should_", "use_")) else False

text = build_system_prompt(FakeAgent())
with open(out_path, "w") as f:
    f.write(text)
print(f"rendered {len(text)} chars -> {out_path}")
