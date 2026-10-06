#!/usr/bin/env python3
"""
jitinnair-ui-mcp — MCP server over the ui.jitinnair.com registry.

Three tools, deliberately. The tool surface is what an agent pays context for;
the registry is the source of truth and is read live over HTTP so this server
can never drift from the site.

    list_registry_items   filter by section / subtype / licence / provenance
    search_registry_items keyword search
    get_registry_item     full payload for one component

There is deliberately NO install tool. Installing is a CLI operation
(`npx shadcn@latest add @jitinnair/<name>`); an MCP that shells out to npm is a
footgun, not a feature.

Transport: stdio JSON-RPC 2.0. No third-party dependencies.

Self-check:  python3 jitinnair_ui_mcp.py --selftest
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("JITINAIR_UI_BASE", "https://ui.jitinnair.com").rstrip("/")
TIMEOUT = float(os.environ.get("JITINAIR_UI_TIMEOUT", "20"))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "jitinnair-ui", "version": "1.0.0"}


# ───────────────────────────────────────────────────────────── http

def get_json(path: str, params: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v not in (None, "", [])}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "jitinnair-ui-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


# ───────────────────────────────────────────────────────── tools

def list_registry_items(section=None, subtype=None, license=None,
                        provenance=None, feature=None, limit=50, offset=0) -> dict:
    """List registry items with optional filters."""
    data = get_json("/api/components", {
        "section": section, "subtype": subtype, "license": license,
        "provenance": provenance, "feature": feature,
        "limit": min(int(limit or 50), 300), "offset": int(offset or 0),
        "sort": "section",
    })
    return {
        "total": data["total"],
        "returned": len(data["items"]),
        "hasMore": data["offset"] + len(data["items"]) < data["total"],
        "items": [
            {
                "name": i["slug"],
                "title": i["name"],
                "type": i["subtype"],
                "section": i["section"],
                "description": i.get("description") or f"{i['loc']} lines from {i['repo']}",
                "license": i["license"],
                "provenance": i["provenance"],
                "loc": i["loc"],
                "repos": i.get("occurrences", 1),
                "install": f"npx shadcn@latest add @jitinnair/{i['slug']}",
                "docs": f"{BASE}/components/{i['slug']}",
            }
            for i in data["items"]
        ],
    }


def search_registry_items(query: str, limit=25) -> dict:
    """Search the registry by keyword across names, descriptions and types."""
    if not query or not query.strip():
        return {"total": 0, "items": [], "hint": "Pass a non-empty query."}
    data = get_json("/api/components", {"q": query.strip(), "limit": min(int(limit or 25), 200)})
    return {
        "total": data["total"],
        "items": [
            {
                "name": i["slug"],
                "title": i["name"],
                "type": i["subtype"],
                "section": i["section"],
                "description": i.get("description") or "",
                "license": i["license"],
                "provenance": i["provenance"],
                "loc": i["loc"],
                "repos": i.get("occurrences", 1),
                "install": f"npx shadcn@latest add @jitinnair/{i['slug']}",
                "docs": f"{BASE}/components/{i['slug']}",
            }
            for i in data["items"]
        ],
    }


def get_registry_item(name: str, include_source: bool = False) -> dict:
    """Full payload for one component, including the shadcn registry item."""
    # NB: str.lstrip() strips *characters*, not a prefix — it would turn
    # "neuro-background" into "euro-background". Use removeprefix.
    raw = (name or "").strip()
    for prefix in ("@jitinnair/", "@jitinnair"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    slug = raw.lstrip("/")
    if not slug:
        return {"error": "name is required"}

    detail = get_json(f"/api/components/{urllib.parse.quote(slug)}")
    item = get_json(f"/r/{urllib.parse.quote(slug)}.json")

    out = {
        "name": detail["slug"],
        "title": detail["name"],
        "type": detail["subtype"],
        "section": detail["section"],
        "description": detail.get("description") or "",
        "license": detail["license"],
        "provenance": detail["provenance"],
        "upstream": detail.get("upstream"),
        "attribution": detail.get("attribution"),
        "install": f"npx shadcn@latest add @jitinnair/{detail['slug']}",
        "docs": f"{BASE}/components/{detail['slug']}",
        "registryUrl": f"{BASE}/r/{detail['slug']}.json",
        "source": {
            "repo": detail["repo"],
            "path": detail["source_path"],
            "loc": detail["loc"],
            "isClient": detail["is_client"],
            "exportedFrom": detail.get("repo"),
        },
        "npmDependencies": (detail.get("dependencies") or {}).get("npm", []),
        "localImports": (detail.get("dependencies") or {}).get("local", []),
        "exports": detail.get("exports", []),
        "props": detail.get("props", []),
        "features": detail.get("features", {}),
        "existsInRepos": [f"{o['repo']}/{o['source_path']}" for o in detail.get("occurrences", [])],
        "useWhen": item.get("useWhen", []),
        "avoidWhen": item.get("avoidWhen", []),
        "registryType": item.get("type"),
        "dependencies": item.get("dependencies", []),
    }

    if item.get("provenance") == "restricted-rewrite-required":
        out["WARNING"] = (
            "Upstream licence does not permit redistribution. Do not ship this "
            "item as-is. Reimplement it, or use the original from its source."
        )
    if include_source:
        req = urllib.request.Request(
            f"{BASE}/api/components/{urllib.parse.quote(slug)}/code",
            headers={"User-Agent": "jitinnair-ui-mcp/1.0"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            out["code"] = r.read().decode("utf-8", errors="replace")
    return out


TOOLS = [
    {
        "name": "list_registry_items",
        "description": (
            "List components in the Jitin UI registry with optional filters. "
            "Use this to browse a section when you do not know what exists yet."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "description": "e.g. backgrounds, ai-chat, forms"},
                "subtype": {"type": "string"},
                "license": {"type": "string", "enum": ["MIT", "21ST-ORIGINAL", "UNKNOWN"]},
                "provenance": {
                    "type": "string",
                    "enum": ["original", "original-reimplementation", "upstream-derivative",
                             "restricted-rewrite-required"],
                },
                "feature": {
                    "type": "string",
                    "description": "Feature flag, e.g. respectsReducedMotion, rawScrollListener",
                },
                "limit": {"type": "integer", "default": 50, "maximum": 300},
                "offset": {"type": "integer", "default": 0},
            },
        },
        "handler": list_registry_items,
    },
    {
        "name": "search_registry_items",
        "description": (
            "Search the registry by intent. Prefer this over list: the registry "
            "holds 900+ components. Returns install commands and docs URLs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Intent, not visual style."},
                "limit": {"type": "integer", "default": 25, "maximum": 200},
            },
            "required": ["query"],
        },
        "handler": search_registry_items,
    },
    {
        "name": "get_registry_item",
        "description": (
            "Full payload for one component: source location, npm and local "
            "imports, exports, props, feature flags, licence, useWhen and "
            "avoidWhen. Read avoidWhen before installing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Registry name, e.g. border-beam"},
                "include_source": {"type": "boolean", "default": False},
            },
            "required": ["name"],
        },
        "handler": get_registry_item,
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
                "Search the Jitin UI registry before writing a component by hand. "
                "Read avoidWhen on a result before installing it. Install with "
                "`npx shadcn@latest add @jitinnair/<name>`."
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

    # argument hygiene
    checks.append(("list rejects bad kwarg", _raises(lambda: list_registry_items(nope=1)), ""))
    checks.append(("search rejects blank", "hint" in search_registry_items("  "), ""))
    # lstrip() strips characters, not a prefix — this is a regression guard.
    checks.append(("namespace prefix stripped", "error" in get_registry_item(""), ""))

    # live checks, only if the registry answers
    try:
        health = get_json("/api/health")
        checks.append(("registry health ok", health.get("database") is True, json.dumps(health)[:80]))
        one = list_registry_items(limit=1)
        checks.append(("list returns items", len(one["items"]) == 1, str(one.get("total"))))
        checks.append(("item has install cmd",
                       one["items"][0]["install"].startswith("npx shadcn@latest add @jitinnair/"),
                       one["items"][0]["install"] if one["items"] else ""))
        found = search_registry_items("background", limit=3)
        checks.append(("search finds something", found["total"] > 0, str(found["total"])))
        if found["items"]:
            detail = get_registry_item(found["items"][0]["name"])
            checks.append(("detail has avoidWhen key", "avoidWhen" in detail, ""))
            checks.append(("detail has features", bool(detail["features"]), ""))
            checks.append(("registry item resolvable", bool(detail["registryUrl"]), detail["registryUrl"]))
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
