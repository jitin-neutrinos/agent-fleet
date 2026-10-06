#!/usr/bin/env python3
"""catalog/upstream-worker.py — refreshes upstream repo stats for every connected item.

For each repo in catalog/upstreams.json (skills + mcps + plugins maps) it records:
  stars, last push, HEAD sha/date on the default branch, latest release tag, checked_at.
Uses the authenticated `gh` CLI (5000 req/h); failures keep the previous values.
Writes catalog/upstream.json. Run daily by agent-fleet-catalog.timer.

Stdlib only.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CAT = Path(__file__).resolve().parent
UPSTREAMS = CAT / "upstreams.json"
TARGET = CAT / "upstream.json"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def gh(*args):
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def main():
    spec = json.loads(UPSTREAMS.read_text())
    repos = set()
    for group in ("skills", "mcps", "plugins"):
        for v in (spec.get(group) or {}).values():
            if v.get("repo"):
                repos.add(v["repo"])
    # auto-derived repos (written by build-inventory.py) — keep stats for those too
    try:
        for r in (json.loads((CAT / "derived-repos.json").read_text()).get("repos") or []):
            repos.add(r)
    except Exception:
        pass
    try:
        prev = (json.loads(TARGET.read_text()).get("repos") or {})
    except Exception:
        prev = {}

    out, ok, fail = {}, 0, 0
    for r in sorted(repos):
        base = gh(f"repos/{r}")
        if not base:
            out[r] = prev.get(r, {"repo": r, "error": "unreachable"})
            out[r]["checked_at"] = NOW
            fail += 1
            continue
        entry = {
            "repo": r,
            "stars": base.get("stargazers_count"),
            "pushed_at": base.get("pushed_at"),
            "default_branch": base.get("default_branch"),
        }
        rel = gh(f"repos/{r}/releases/latest")
        entry["latest_tag"] = (rel or {}).get("tag_name") or ""
        head = gh(f"repos/{r}/commits/{entry.get('default_branch') or 'main'}")
        if head:
            entry["head_sha"] = (head.get("sha") or "")[:10]
            entry["head_date"] = ((head.get("commit") or {}).get("committer") or {}).get("date", "")
        entry["checked_at"] = NOW
        out[r] = entry
        ok += 1
        time.sleep(0.2)

    # skip the rewrite when nothing but timestamps changed (keeps sync commits meaningful)
    def strip(d):
        return {k: {kk: vv for kk, vv in v.items() if kk != "checked_at"} for k, v in d.items()}
    if prev and strip(prev) == strip(out):
        print(f"[upstream] unchanged ({ok} ok, {fail} failed of {len(repos)}) — keeping existing {TARGET.name}")
        return
    TARGET.write_text(json.dumps({"generated_at": NOW, "repos": out}, indent=1))
    old = sum(1 for r in repos if r in prev)
    print(f"[upstream] {ok} ok, {fail} failed of {len(repos)} repos ({old} previously known) -> {TARGET}")

if __name__ == "__main__":
    main()
