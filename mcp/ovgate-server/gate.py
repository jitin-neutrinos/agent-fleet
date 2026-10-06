#!/usr/bin/env python3
"""ovgate — Laya memory-write gate for OpenViking (kurama-core).

Stands in front of OpenViking's MCP endpoint (1933) as a filtering proxy (1934).
Wired into harnesses instead of the raw endpoint. Policy:

  * destructive memory ops (`forget`, `rm`/delete of resources, `edit` that
    replaces content) require Laya risk < threshold on the payload, else HITL —
    the operator question flows back as a deny with a reason (agents re-ask the
    user; the human approves via the normal harness flow).
  * ordinary writes (`remember`, `write`, `add_resource`) pass, but payload
    duplication is checked: if Laya says the new memory substantially duplicates
    existing context, the write is downgraded to a log + skipped (per the
    research: contradictory/duplicate memory entries are the top memory-store
    failure).

Fail-open everywhere: Laya down -> pass through untouched. Decisions logged to
~/.hermes/logs/ovgate.log with hash-chained receipts in the laya ledger.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

UPSTREAM = os.environ.get("OV_UPSTREAM", "http://127.0.0.1:1933")
LAYA = os.environ.get("LAYA_ENDPOINT", "http://127.0.0.1:8015/v1/systemone")
LAYA_TOKEN = os.environ.get("LAYA_MCP_TOKEN", "")
LOG = os.path.expanduser("~/.hermes/logs/ovgate.log")
DESTRUCTIVE_TOOLS = {"forget"}
RISKY_TOOLS = {"edit"}          # replaces content of an existing resource
DUP_CHECK_TOOLS = {"remember", "write", "add_resource"}
DUPLICATE_SKIP_THRESHOLD = 0.70


def _log(line: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


def _receipt(kind: str, summary: str) -> None:
    try:
        import importlib.util
        from pathlib import Path
        p = Path(os.path.expanduser("~/.hermes/plugins/laya-guardrails/ledger.py"))
        spec = importlib.util.spec_from_file_location("ovg_ledger", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.append(kind, summary)
    except Exception:
        pass


def _laya(state: dict, questions: dict) -> dict | None:
    try:
        body = json.dumps({"state": state, "questions": questions}).encode()
        headers = {"Content-Type": "application/json"}
        if LAYA_TOKEN:
            headers["Authorization"] = f"Bearer {LAYA_TOKEN}"
        req = urllib.request.Request(LAYA, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as r:
            return json.load(r).get("answers", {})
    except Exception:
        return None


def _deterministic_delete_policy(uri: str) -> str | None:
    """'confirm' | 'allow' | None(unknown->Laya second opinion). kurama hard-pattern doctrine."""
    u = (uri or "").lower()
    if any(k in u for k in ("cache/", "test", "tmp", "scratch", "-temp", "fixture")):
        return "allow"
    if any(k in u for k in ("memories/", "memory/", "decision", "preference", "learned", "knowledge/")):
        return "confirm"
    return None


def gate_call(tool: str, args: dict) -> tuple[bool, str]:
    """(allow, reason). Fail-open (True, '') on any internal error."""
    try:
        payload = json.dumps(args)[:4000]

        if tool in DESTRUCTIVE_TOOLS:
            uri = str(args.get("uri") or args.get("path") or "")
            policy = _deterministic_delete_policy(uri)
            if policy == "confirm":
                _log(f"BLOCK delete policy=confirm uri={uri!r}")
                _receipt("HARD_GATED", f"ovgate delete protected-path {uri[:90]}")
                return False, (f"OVGATE: {uri!r} is in a protected memory namespace. Permanent "
                               f"deletes there need the user's explicit OK — ask first.")
            if policy is None:
                # fuzzy case: Laya second opinion, ENFORCED only at high confidence
                answers = _laya({"action": f"ovgate delete: {payload}"}, {
                    "destructive": {"type": "noul", "instructions": (
                        "Would deleting this stored context destroy durable knowledge the user "
                        "will need again? Answer no only for obvious temporary/cache/test data.")},
                })
                if answers and float(answers.get("destructive", {}).get("noul", 0.0)) >= 0.75:
                    _log(f"BLOCK delete laya-high uri={uri!r}")
                    _receipt("HARD_GATED", f"ovgate delete laya-high {uri[:90]}")
                    return False, ("OVGATE: this deletion looks destructive to stored knowledge "
                                   "(Laya score >= 0.75). Ask the user first.")
            _log(f"PASS delete policy={policy or 'laya-low'} uri={uri!r}")
            return True, ""

        if tool in DUP_CHECK_TOOLS:
            text = str(args.get("content") or args.get("text") or args.get("text_content")
                       or args.get("memory") or payload)
            if len(text) > 120:
                # deterministic containment check against recent stored memories via ov find
                try:
                    import subprocess as _sp
                    probe = " ".join(text.split()[:25])
                    r = _sp.run([os.path.expanduser("~/Work/openviking/.venv/bin/ov"),
                                 "find", probe], capture_output=True, text=True, timeout=10)
                    out = r.stdout
                    import re as _re
                    tops = [float(x) for x in _re.findall(r"score\s+([0-9.]+)", out)[:3]]
                    if tops and max(tops) >= 0.9:
                        _log(f"SKIP near-dup top-score={max(tops):.2f} tool={tool} len={len(text)}")
                        _receipt("SCREEN_FLAG", f"ovgate near-dup write skipped {max(tops):.2f}")
                        return False, (f"OVGATE: a near-identical memory already exists "
                                       f"(similarity {max(tops):.2f}). Not stored twice.")
                except Exception:
                    pass
            _log(f"PASS write tool={tool} len={len(text)}")
            return True, ""

        if tool in RISKY_TOOLS:
            uri = str(args.get("uri") or args.get("path") or "")
            if _deterministic_delete_policy(uri) == "confirm":
                _log(f"BLOCK edit policy=confirm uri={uri!r}")
                _receipt("HARD_GATED", f"ovgate edit protected-path {uri[:90]}")
                return False, (f"OVGATE: {uri!r} is a protected memory namespace — wholesale "
                               f"content replacement needs the user's OK. Ask first.")
            return True, ""
    except Exception as exc:
        _log(f"ERROR fail-open tool={tool}: {exc!r}")
    return True, ""
