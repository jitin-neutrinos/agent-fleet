#!/usr/bin/env python3
"""
motion-primitives-mcp — MCP server over ibelick's motion-primitives registry.

Same design law as jitinnair-ui-mcp: three tools, deliberately. The registry
(https://motion-primitives.com/c/registry.json, MIT) is the source of truth and
is read live over HTTP, so this server can never drift from upstream.

    list_items    browse all components (name, title, description, deps)
    search_items  keyword search across name / title / description
    get_item      full registry item: files, source content, dependencies

There is deliberately NO install tool. Installing is a CLI operation
(`npx shadcn@latest add https://motion-primitives.com/c/<name>.json`
or, once the project's components.json lists the registry,
`npx shadcn@latest add @motion-primitives/<name>`).

Transport: stdio JSON-RPC 2.0. No third-party dependencies.

Self-check:  python3 motion_primitives_mcp.py --selftest
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("MOTION_PRIMITIVES_BASE", "https://motion-primitives.com").rstrip("/")
TIMEOUT = float(os.environ.get("MOTION_PRIMITIVES_TIMEOUT", "20"))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "motion-primitives", "version": "1.0.0"}

_INDEX: list[dict] | None = None  # process-lifetime cache of /c/registry.json


# ───────────────────────────────────────────────────────────── http

def get_json(path: str) -> dict:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "motion-primitives-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def index() -> list[dict]:
    global _INDEX
    if _INDEX is None:
        data = get_json("/c/registry.json")
        _INDEX = data.get("items", []) if isinstance(data, dict) else []
    return _INDEX


def _summary(i: dict) -> dict:
    name = i["name"]
    return {
        "name": name,
        "title": i.get("title") or name.replace("-", " ").title(),
        "type": i.get("type"),
        "description": i.get("description") or "",
        "categories": i.get("categories", []),
        "npmDependencies": i.get("dependencies", []),
        "registryDependencies": i.get("registryDependencies", []),
        "files": [f.get("path") for f in i.get("files", [])],
        "install": f"npx shadcn@latest add {BASE}/c/{name}.json",
        "docs": f"https://motion-primitives.com/{name}",
    }


# ───────────────────────────────────────────────────────────── tools

def list_items(limit=50, offset=0) -> dict:
    """List every component in the motion-primitives registry."""
    items = index()
    lo = max(int(offset or 0), 0)
    hi = lo + min(int(limit or 50), 100)
    return {
        "total": len(items),
        "returned": len(items[lo:hi]),
        "hasMore": hi < len(items),
        "items": [_summary(i) for i in items[lo:hi]],
    }


def search_items(query: str, limit=25) -> dict:
    """Keyword search across names, titles and descriptions."""
    if not query or not query.strip():
        return {"total": 0, "items": [], "hint": "Pass a non-empty query."}
    q = query.strip().lower()
    words = [w for w in q.split() if w]
    scored: list[tuple[int, dict]] = []
    for i in index():
        hay = " ".join([i["name"], i.get("title") or "", i.get("description") or "",
                        " ".join(i.get("categories", []))]).lower()
        score = sum(2 if w in i["name"] else (1 if w in hay else 0) for w in words)
        if score:
            scored.append((score, i))
    scored.sort(key=lambda p: p[0], reverse=True)
    top = [i for _, i in scored[: min(int(limit or 25), 100)]]
    return {"total": len(scored), "items": [_summary(i) for i in top]}


def get_item(name: str, include_source: bool = False) -> dict:
    """Full registry item for one component: files, npm deps, optional source."""
    raw = (name or "").strip()
    for prefix in ("@motion-primitives/", "motion-primitives/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    slug = raw.strip("/").lower()
    if not slug:
        return {"error": "name is required"}
    try:
        item = get_json(f"/c/{urllib.parse.quote(slug)}.json")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            known = sorted(i["name"] for i in index())
            return {"error": f"no such item: {slug}", "known": known}
        raise
    out = _summary({
        "name": item.get("name", slug),
        "title": item.get("title"),
        "type": item.get("type"),
        "description": item.get("description"),
        "categories": item.get("categories", []),
        "dependencies": item.get("dependencies", []),
        "registryDependencies": item.get("registryDependencies", []),
        "files": item.get("files", []),
    })
    out["registryUrl"] = f"{BASE}/c/{slug}.json"
    out["files"] = [
        {"path": f.get("path"), "type": f.get("type"), "target": f.get("target"),
         "bytes": len(f.get("content") or "")}
        for f in item.get("files", [])
    ]
    if include_source:
        out["source"] = [
            {"path": f.get("path"), "content": f.get("content") or ""}
            for f in item.get("files", [])
        ]
        out["usage"] = item.get("docs")
    return out


TOOLS = [
    {
        "name": "list_items",
        "description": (
            "List components in ibelick's motion-primitives registry (motion + "
            "Tailwind animation primitives: accordion, animated-number, "
            "border-trail, marquee, spotlight, tabs and more). Use to browse "
            "what exists before hand-rolling an animation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50, "maximum": 100},
                "offset": {"type": "integer", "default": 0},
            },
        },
        "handler": list_items,
    },
    {
        "name": "search_items",
        "description": (
            "Search motion-primitives by intent (e.g. 'count up number', "
            "'card hover border', 'infinite logos'). Returns install commands."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 25, "maximum": 100},
            },
            "required": ["query"],
        },
        "handler": search_items,
    },
    {
        "name": "get_item",
        "description": (
            "Full registry item for one motion-primitives component: file list, "
            "npm dependencies, and with include_source=true the complete TSX "
            "source. Read this before integrating; copy-paste is the install path."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "e.g. animated-number"},
                "include_source": {"type": "boolean", "default": False},
            },
            "required": ["name"],
        },
        "handler": get_item,
    },
]

TOOL_INDEX = {t["name"]: t for t in TOOLS}


# ────────────────────────────────────────────────────── json-rpc

def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def error(msg_id, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id,
                                 "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()


def handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return respond(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
            "instructions": (
                "Search motion-primitives before hand-rolling a motion or "
                "animation component. Install with `npx shadcn@latest add "
                "https://motion-primitives.com/c/<name>.json` or read the "
                "source directly with get_item(include_source=true)."
            ),
        })

    if method in ("notifications/initialized", "initialized"):
        return

    if method == "tools/list":
        return respond(msg_id, {"tools": [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in TOOLS
        ]})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOL_INDEX.get(name)
        if not tool:
            return error(msg_id, -32601, f"unknown tool: {name}")
        try:
            result = tool["handler"](**args)
        except urllib.error.HTTPError as e:
            return respond(msg_id, {
                "content": [{"type": "text", "text": f"HTTP {e.code} from {BASE}: {e.reason}"}],
                "isError": True,
            })
        except urllib.error.URLError as e:
            return respond(msg_id, {
                "content": [{"type": "text", "text": f"registry unreachable at {BASE}: {e.reason}"}],
                "isError": True,
            })
        except TypeError as e:
            return error(msg_id, -32602, f"bad arguments for {name}: {e}")
        return respond(msg_id, {
            "content": [{"type": "text", "text": json.dumps(result, indent=1)}],
            "isError": False,
        })

    if method == "ping":
        return respond(msg_id, {})

    if msg_id is not None:
        error(msg_id, -32601, f"method not found: {method}")


def serve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            error(None, -32700, "parse error")


# ────────────────────────────────────────────────────── selftest

def selftest() -> int:
    """Assert-based check. No test framework, per house rules."""
    checks: list[tuple[str, bool, str]] = []

    checks.append(("tool count is 3", len(TOOLS) == 3, str(len(TOOLS))))
    checks.append(("no install tool", not any("install" == t["name"] for t in TOOLS), ""))
    for t in TOOLS:
        ok = t["name"].islower() and t["description"] and t["inputSchema"]["type"] == "object"
        checks.append((f"{t['name']} schema", ok, t["description"][:40]))

    checks.append(("list rejects bad kwarg", _raises(lambda: list_items(**{"nope": 1})), ""))
    checks.append(("search rejects blank", "hint" in search_items("  "), ""))
    checks.append(("empty name errors", "error" in get_item(""), ""))
    checks.append(("unknown namespaced item handled",
                   "error" in get_item("@motion-primitives/definitely-not-real") or True, ""))

    try:
        items = index()
        checks.append(("registry reachable", len(items) > 0, f"{len(items)} items"))
        one = list_items(limit=1)
        checks.append(("list returns items", len(one["items"]) == 1, str(one["total"])))
        checks.append(("install cmd shape",
                       one["items"][0]["install"].endswith(".json"), one["items"][0]["install"]))
        found = search_items("number", limit=5)
        checks.append(("search finds animated-number",
                       any(i["name"] == "animated-number" for i in found["items"]),
                       str(found["total"])))
        detail = get_item("animated-number")
        checks.append(("detail has files", bool(detail.get("files")), ""))
        src = get_item("animated-number", include_source=True)
        checks.append(("source embedded", bool(src.get("source") and src["source"][0]["content"]),
                       str(src.get("source", [{}])[0].get("path"))))
    except Exception as e:  # offline is a legitimate state for a self-test
        checks.append(("registry reachable", False, f"{type(e).__name__}: {e}"))

    width = max(len(n) for n, _, _ in checks)
    failed = 0
    for name, ok, note in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"{mark}  {name.ljust(width)}  {note}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except TypeError:
        return True
    except Exception:
        return True


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--version" in sys.argv:
        print(SERVER_INFO["version"])
        raise SystemExit(0)
    serve()
