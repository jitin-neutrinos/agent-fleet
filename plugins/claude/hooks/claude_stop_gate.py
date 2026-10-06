#!/usr/bin/env python3
"""Claude Code Stop hook — Laya done-gate (Tier 1).

Fires when Claude Code is about to end its turn. If the final response claims
completion and the session's recent activity does not plausibly support it,
emit {"decision": "block", "reason": ...} to keep the turn going (Claude Code
Stop-gate contract). Fail-open: any error -> exit 0 with empty output.

Reads Stop payload JSON from stdin:
    { "session_id": "...", "transcript_path": "...", "stop_hook_active": bool }
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request

LOG = os.path.expanduser("~/.claude/logs/laya-donegate.log")
ENDPOINT = os.environ.get("LAYA_ENDPOINT", "http://127.0.0.1:8015/v1/systemone")
CLAIM_RE = re.compile(
    r"(?i)\b(done|complete[d]?|all (tests? )?pass|fixed|implemented|working|deployed|verified)\b")
SUPPORT_RE = re.compile(
    r"(?i)(pytest|npm (run )?(build|test)|make|cargo (build|test)|go (build|test)|"
    r"curl .*(/health|/api)|systemctl status|git diff|docker (ps|logs))")


def _log(line: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


def _tail_transcript_commands(path: str, limit: int = 25) -> list[str]:
    """Pull the most recent assistant/tool text snippets from the transcript jsonl."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 400_000))
            lines = fh.read().decode("utf-8", "replace").splitlines()
        out = []
        for ln in lines[-80:]:
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                continue
            msg = obj.get("message") or {}
            content = msg.get("content")
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        inp = c.get("input") or {}
                        out.append(str(inp.get("command") or inp.get("file_path") or c.get("name", ""))[:200])
            elif isinstance(obj.get("toolName"), str):
                out.append(str(obj.get("toolInput", {}).get("command", ""))[:200])
        return [c for c in out if c][-limit:]
    except Exception:
        return []


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if payload.get("stop_hook_active"):
        return  # our own nudge already ran once; never loop
    resp = str(payload.get("last_message") or payload.get("final_response") or "")
    # Claude Code Stop payload carries transcript; last assistant text is in it
    transcript = str(payload.get("transcript_path") or "")
    if not resp and transcript:
        try:
            with open(transcript, "rb") as fh:
                fh.seek(0, 2)
                fh.seek(max(0, fh.tell() - 200_000))
                for ln in reversed(fh.read().decode("utf-8", "replace").splitlines()):
                    try:
                        obj = json.loads(ln)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    if msg.get("role") == "assistant":
                        c = msg.get("content")
                        if isinstance(c, list):
                            txt = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
                        else:
                            txt = str(c or "")
                        if txt.strip():
                            resp = txt
                            break
        except Exception:
            pass
    if not resp or not CLAIM_RE.search(resp[:4000]):
        return

    activity = _tail_transcript_commands(transcript) if transcript else []
    evidence = [a for a in activity if SUPPORT_RE.search(a)]
    if not evidence:
        # nothing in the transcript looks like verification activity
        verdict_p = 0.20
    else:
        try:
            # per-item scoring: the base model's multi-item evidence scoring is unstable
            # (3+ items can invert); max over single-item scores is clean. Fine-tune replaces this.
            verdict_p = 0.0
            for ev in evidence[:5]:
                body = json.dumps({"state": {"claims": resp[:2500], "evidence": [ev]},
                                   "questions": {"supported": {"type": "noul", "instructions": (
                                       "Does the recorded activity plausibly support the completion claims in the text?")}}}).encode()
                req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as r:
                    answers = json.load(r).get("answers", {})
                verdict_p = max(verdict_p, float(answers.get("supported", {}).get("noul", 0.0)))
        except Exception:
            return  # Laya down -> fail open
    if verdict_p < 0.35:
        _log(f"NUDGE supported={verdict_p:.2f} resp={resp[:90]!r}")
        print(json.dumps({"decision": "block", "reason": (
            "Done-gate: your completion claims do not match the session's recorded activity "
            f"(support {verdict_p:.2f}). Run the checks that prove the claim (tests, build, "
            "health call, diff) or restate what you actually verified before ending.")}))
    else:
        _log(f"OK supported={verdict_p:.2f}")


if __name__ == "__main__":
    main()
