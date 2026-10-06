#!/usr/bin/env python3
"""slopguard hook for Antigravity (agy) — deterministic anti-slop enforcement.

Registered via ~/.gemini/config/hooks.json (PreToolUse) and/or
~/.gemini/settings.json "BeforeTool". Reads the tool-call JSON from stdin
(camelCase keys, tolerate snake_case), prints a decision JSON on stdout:

    {"decision": "allow"}
    {"decision": "deny", "reason": "..."}

Checks (same as the Hermes/Claude/opencode slopguard):
  1. Secrets in file writes (.env exempt).
  2. Package installs whose package does not exist in npm/PyPI (slopsquatting).
Fail-open on any internal error: prints allow.
"""
import json
import re
import sys
import urllib.request

SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"(?i)(aws)?_?secret_?access_?key\s*[:=]\s*['\"][A-Za-z0-9/+=]{32,}['\"]"), "AWS secret access key"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"(?i)\b(api_?key|secret|token|passwd|password)\b\s*[:=]\s*['\"][A-Za-z0-9+/_-]{24,}['\"]"), "hardcoded credential"),
]
_PLACEHOLDER = re.compile(r"(?i)(?:\b|')(?:x{3,}|example|placeholder|changeme|dummy|your[-_][a-z]*|<[^>]+>)(?:\b|')")
_ENV_PATH = re.compile(r"(?i)\.env(\.|$)|/secrets?/|credentials")
_SEP = r"[\s'\"\[\],()]"
NPM_RE = re.compile(rf"\b(?:npm|i|yarn|pnpm)(?:{_SEP}+add|{_SEP}+install|{_SEP}+i){_SEP}+([^&|;]+)|\bnpx{_SEP}+-?y?{_SEP}+(@?[\w@/.-]+)")
PY_RE = re.compile(rf"\b(?:pip3?|uv)(?:{_SEP}+pip)?{_SEP}+install{_SEP}+([^&|;\]]+)|\buv{_SEP}+add{_SEP}+([^&|;\]]+)")
_PKG = re.compile(r"(?<![\w./-])(@?[\w][\w.-]*)(?:@[><=!~^]?[\w.]+)?")

_cache = {}


def _pkg_exists(registry, name):
    key = f"{registry}:{name}"
    if key in _cache:
        return _cache[key]
    url = f"https://registry.npmjs.org/{name}" if registry == "npm" else f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=4) as r:
            ok = r.status == 200
    except urllib.error.HTTPError as e:
        ok = False if e.code == 404 else None
    except Exception:
        ok = None
    _cache[key] = ok
    return ok


def _check_packages(command):
    targets = []
    m = NPM_RE.search(command)
    if m:
        if m.group(2):
            targets.append(("npm", m.group(2)))
        else:
            for raw in (m.group(1) or "").split():
                if raw.startswith("-"):
                    continue
                p = _PKG.match(raw.strip("\"'-,"))
                if p:
                    targets.append(("npm", p.group(1)))
    m = PY_RE.search(command)
    if m:
        for raw in (m.group(1) or m.group(2) or "").split():
            if raw.startswith("-"):
                continue
            p = _PKG.match(raw.strip("\"',"))
            if p:
                base = re.split(r"[\[=<>!~;]", p.group(1))[0]
                if base:
                    targets.append(("pypi", base))
    for registry, name in targets:
        name = name.rstrip("/")
        if ok := _pkg_exists(registry, name):
            continue
        if ok is False:
            return name
    return None


def decide(payload):
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    args = payload.get("tool_input") or payload.get("args") or payload.get("input") or payload
    command = str(args.get("command") or args.get("script") or args.get("code") or "")
    path = str(args.get("path") or args.get("file_path") or args.get("filePath") or "")
    content = str(args.get("content") or args.get("new_string") or "")

    if command.strip():
        bad = _check_packages(command)
        if bad:
            return {"decision": "deny", "reason": (
                f"SLOPGUARD: package '{bad}' does not exist in its registry — "
                f"hallucinated packages are an attack vector (slopsquatting). "
                f"Check the real package name and retry.")}

    if content and path and not _ENV_PATH.search(path):
        blob = f"{path}\n{content}"
        for pat, reason in SECRET_PATTERNS:
            hit = pat.search(blob)
            if hit and not _PLACEHOLDER.search(hit.group(0)):
                return {"decision": "deny", "reason": (
                    f"SLOPGUARD: {reason} in plaintext write to {path}. "
                    f"Move it to an environment file (.env / secrets dir) and "
                    f"reference it by name.")}
    return {"decision": "allow"}


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        out = decide(payload)
    except Exception:
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
