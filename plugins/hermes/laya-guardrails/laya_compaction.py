"""laya_compaction — Laya-scored keep/drop for Hermes context compaction.

The V1-video feature: when Hermes compacts (demoting old tool results to 1-line
summaries), ask the local Laya decision engine what the result primarily
contains. Decisions/errors/paths keep a key line alongside the summary; listings
and chatter get the standard one-liner. Laya down/slow (1.5s) -> standard summary.

Config (config.yaml, optional):
  laya_compaction:
    endpoint: http://127.0.0.1:8015/v1/systemone
    timeout_s: 1.5
    keep_chars: 700        # budget for the kept key line
    disabled: false

Loaded BY the patch inside context_compressor._summarize_tool_result; on any
failure compression behaves exactly like stock Hermes.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

_DOWN_UNTIL = 0.0  # circuit breaker after a failed call
_KEEP_KINDS = {"decision", "error", "path"}


def _cfg() -> dict:
    try:
        from hermes_constants import get_hermes_home
        import yaml
        with open(get_hermes_home() / "config.yaml") as fh:
            raw = (yaml.safe_load(fh) or {}).get("laya_compaction") or {}
    except Exception:
        raw = {}
    cfg = {"endpoint": "http://127.0.0.1:8015/v1/systemone",
           "timeout_s": 1.5, "keep_chars": 700, "disabled": False}
    cfg.update({k: v for k, v in raw.items() if v is not None})
    return cfg


def laya_keep_verdict(tool_content: str) -> dict | None:
    """Classify the result. Returns {"kind": str, "keep": bool} or None."""
    global _DOWN_UNTIL
    if time.time() < _DOWN_UNTIL:
        return None
    cfg = _cfg()
    if cfg.get("disabled"):
        return None
    body = json.dumps({
        "state": {"result": str(tool_content)[:5000]},
        "questions": {
            "kind": {"type": "choice", "instructions": (
                "What does this tool result primarily contain?"),
                "criteria": {
                    "decision": "a decision, sign-off, commitment, chosen approach, or key fact that must be remembered",
                    "error": "a failure, stack trace, or error that must not be forgotten",
                    "path": "a concrete file path, command, id, or pointer the agent will need",
                    "listing": "bulk tabular, directory, or log output whose gist fits one line",
                    "chatter": "status updates, progress, or conversation",
                }},
        },
    }).encode()
    req = urllib.request.Request(cfg["endpoint"], data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=float(cfg["timeout_s"])) as resp:
            answers = json.load(resp).get("answers", {})
        kind = str(answers.get("kind", {}).get("choice") or "listing")
        return {"kind": kind, "keep": kind in _KEEP_KINDS}
    except Exception:
        _DOWN_UNTIL = time.time() + 60.0
        return None


def enrich_summary(summary: str, tool_name: str, tool_args: str, tool_content: str) -> str:
    """Return an upgraded summary when Laya says the entry holds durable value."""
    # Summaries with exact-format contracts downstream (clarify/steer sentinels,
    # single-line skill_manage rows): never enrich those.
    if summary.startswith(("[clarify]", "[steer]", "[skill_manage]")):
        return summary
    verdict = laya_keep_verdict(tool_content)
    if not verdict or not verdict.get("keep"):
        return summary
    keep_chars = int(_cfg()["keep_chars"])
    key_line = ""
    for line in str(tool_content).splitlines():
        s = line.strip()
        if len(s) > 12:
            key_line = s[:keep_chars]
            break
    if not key_line or key_line in summary:
        return summary
    # single-line append: many summaries carry one-line format contracts
    key_line = key_line.replace("\n", " ")
    return f"{summary} [laya-kept:{verdict['kind']}] {key_line}"
