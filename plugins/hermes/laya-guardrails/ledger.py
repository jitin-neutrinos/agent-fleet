"""Hash-chained decision receipts for the Laya guardrails (Tier 2).

Append-only JSONL ledger at ~/.hermes/logs/laya-receipts.jsonl.
Each entry: {seq, ts, kind, summary, prev, hash} where hash = sha256(prev_hash + canonical(entry minus hash)).
Any edit/delete of a past line makes verify_chain() return False — tamper-evidence by structure.

CLI:
    python3 ledger.py append KIND SUMMARY
    python3 ledger.py verify
    python3 ledger.py tail [N]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

LEDGER = os.path.expanduser("~/.hermes/logs/laya-receipts.jsonl")

KINDS = {
    "HARD_GATED", "LAYA_CONFIRM", "LOOP_BLOCKED", "VERIFY_NUDGE",
    "DRIFT_WARN", "INBOUND_FLAG", "SCREEN_FLAG", "GENESIS",
}


def _canonical(entry: dict) -> str:
    e = {k: v for k, v in entry.items() if k != "hash"}
    return json.dumps(e, sort_keys=True, separators=(",", ":"))


def _entry_hash(entry: dict) -> str:
    return hashlib.sha256(_canonical(entry).encode()).hexdigest()


def append(kind: str, summary: str, path: str = LEDGER) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    entries = _read_all(path)
    prev = entries[-1]["hash"] if entries else "0" * 64
    entry = {
        "seq": len(entries) + 1,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": kind,
        "summary": summary[:300],
        "prev": prev,
    }
    entry["hash"] = _entry_hash(entry)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return entry


def _read_all(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"corrupt": True, "raw": line[:120]})
    return out


def verify_chain(path: str = LEDGER) -> dict:
    entries = _read_all(path)
    prev = "0" * 64
    for n, e in enumerate(entries, 1):
        if e.get("corrupt") or e.get("hash") != _entry_hash(e) or e.get("prev") != prev or e.get("seq") != n:
            return {"chain_intact": False, "entries": len(entries), "broke_at": n}
        prev = e["hash"]
    return {"chain_intact": True, "entries": len(entries), "broke_at": None}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "append" and len(sys.argv) >= 4:
        print(json.dumps(append(sys.argv[2], " ".join(sys.argv[3:]))))
    elif cmd == "verify":
        print(json.dumps(verify_chain()))
    elif cmd == "tail":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        for e in _read_all(LEDGER)[-n:]:
            print(f"{e.get('seq', '?'):>4} {e.get('ts', '?')} {e.get('kind', '?'):<13} {e.get('summary', '')[:110]}")
    else:
        print(__doc__)
