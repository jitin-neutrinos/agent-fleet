#!/usr/bin/env python3
"""catalog/docs-worker.py — keeps official upstream docs in the store, refreshed daily.

For every upstream repo (curated in upstreams.json + auto-derived in derived-repos.json)
it fetches the repo README via `gh api repos/<r>/readme` (works for private repos too),
renders nothing here — stores raw markdown + metadata:
    catalog/docs/<owner>__<repo>.json = {repo, branch, path, fetched_at, sha, md}
Rewrites only when the README content actually changed (sha of the markdown).
Run daily by agent-fleet-catalog.timer; re-run any time (`python3 catalog/docs-worker.py`).
Stdlib only.
"""
import base64
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CAT = Path(__file__).resolve().parent
DOCS = CAT / "docs"
MAX_MD = 300_000  # cap stored readme size


def gh(*args, timeout=45):
    p = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=timeout)
    return p.stdout if p.returncode == 0 else None


def repo_set():
    repos = {}
    # curated map may carry a docs override: {"repo": ..., "docs_path": "docs/INSTALL.md"}
    try:
        spec = json.loads((CAT / "upstreams.json").read_text())
        for group in ("skills", "mcps", "plugins"):
            for v in (spec.get(group) or {}).values():
                if v.get("repo"):
                    repos[v["repo"]] = v.get("docs_path") or ""
    except Exception:
        pass
    # auto-derived repos from skill frontmatter (written by build-inventory.py)
    try:
        for r in (json.loads((CAT / "derived-repos.json").read_text()).get("repos") or []):
            repos.setdefault(r, "")
    except Exception:
        pass
    return repos


def main():
    DOCS.mkdir(exist_ok=True)
    repos = repo_set()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok = skip = fail = 0
    for repo, docs_path in sorted(repos.items()):
        out_file = DOCS / (repo.replace("/", "__") + ".json")
        raw = None
        path_used = ""
        if docs_path:
            data = gh(f"repos/{repo}/contents/{docs_path}")
            if data:
                try:
                    j = json.loads(data)
                    raw = base64.b64decode(j.get("content") or "").decode("utf-8", "replace")
                    path_used = docs_path
                except Exception:
                    raw = None
        if raw is None:
            data = gh(f"repos/{repo}/readme")
            if data:
                try:
                    j = json.loads(data)
                    raw = base64.b64decode(j.get("content") or "").decode("utf-8", "replace")
                    path_used = j.get("path") or "README.md"
                except Exception:
                    raw = None
        if raw is None:
            fail += 1
            continue
        raw = raw[:MAX_MD]
        sha = hashlib.sha256(raw.encode()).hexdigest()[:12]
        old = None
        try:
            old = json.loads(out_file.read_text())
        except Exception:
            pass
        if old and old.get("sha") == sha:
            skip += 1
            continue
        try:
            branch = json.loads((CAT / "upstream.json").read_text()).get("repos", {}).get(repo, {}).get("default_branch") or "main"
        except Exception:
            branch = "main"
        out_file.write_text(json.dumps({
            "repo": repo, "branch": branch, "path": path_used,
            "fetched_at": now, "sha": sha, "md": raw,
        }))
        ok += 1
        time.sleep(0.15)
    print(f"[docs] {ok} updated, {skip} unchanged, {fail} failed of {len(repos)} repos -> {DOCS}")


if __name__ == "__main__":
    sys.exit(main())
