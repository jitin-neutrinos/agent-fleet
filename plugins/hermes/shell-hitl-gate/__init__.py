"""Force every shell command through a human-approval gate.

Coding profiles (coder -> claude -p, reviewer -> agy -p) get ONE bulk
approval per session that then covers every command they run. Every other
profile (default, ops, researcher, desktop, ...) is gated per distinct
command - no shell call runs silently, dangerous or not.
"""

from __future__ import annotations

import hashlib

GATED_TOOLS = {"terminal", "execute_code"}
BULK_APPROVAL_PROFILES = {"coder", "reviewer"}


def _active_profile() -> str:
    try:
        from hermes_cli.profiles import get_active_profile_name

        return get_active_profile_name()
    except Exception:
        return "default"


def _command_text(args: dict) -> str:
    args = args or {}
    for key in ("command", "code", "script"):
        value = args.get(key)
        if value:
            return str(value)
    return str(args)


def gate_shell_command(tool_name: str, args: dict, task_id: str = "", **kwargs):
    del task_id, kwargs
    if tool_name not in GATED_TOOLS:
        return None

    profile = _active_profile()

    if profile in BULK_APPROVAL_PROFILES:
        return {
            "action": "approve",
            "message": (
                f"Coding task on profile '{profile}' wants shell access. "
                "Approve once to cover every command this session."
            ),
            "rule_key": "coding-bulk",
        }

    command_text = _command_text(args)
    digest = hashlib.sha256(command_text.encode("utf-8", "ignore")).hexdigest()[:16]
    return {
        "action": "approve",
        "message": (
            f"Profile '{profile}' wants to run a shell command:\n"
            f"{command_text[:300]}"
        ),
        "rule_key": f"{tool_name}:{digest}",
    }


def register(ctx):
    ctx.register_hook("pre_tool_call", gate_shell_command)
