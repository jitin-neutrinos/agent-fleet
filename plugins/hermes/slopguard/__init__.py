"""slopguard — deterministic anti-slop enforcement for Hermes (port of manpreet171/slopguard).

Two hard gates, no LLM, fail-open on network errors:
  1. Secret scan on file-write/patch/code tools — hardcoded keys never land in source.
     (.env-style files are exempt: that is where keys belong.)
  2. Registry check before package installs — a 404 from npm/PyPI is a hallucinated
     package (slopsquatting); the install is blocked before it runs.

Every block is logged to ~/.hermes/logs/slopguard.log.
"""
import json
import os
import re
import time
import urllib.request

LOG = os.path.expanduser("~/.hermes/logs/slopguard.log")
_cache: dict[str, bool] = {}

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


def _log(line: str) -> None:
    try:
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n")
    except OSError:
        pass


def _strings(args: dict, depth: int = 0) -> list[str]:
    out: list[str] = []
    if depth > 3:
        return out
    if isinstance(args, dict):
        for k, v in args.items():
            if k in ("path", "file_path"):
                continue  # paths scanned separately
            out.extend(_strings(v, depth + 1))
    elif isinstance(args, list):
        for v in args:
            out.extend(_strings(v, depth + 1))
    elif isinstance(args, str):
        out.append(args)
    return out


def _path_of(args: dict) -> str:
    for k in ("path", "file_path", "filepath"):
        v = args.get(k)
        if isinstance(v, str):
            return v
    return ""


def _pkg_exists(registry: str, name: str) -> bool | None:
    """True/False from the registry; None = could not check (fail-open)."""
    key = f"{registry}:{name}"
    if key in _cache:
        return _cache[key]
    url = f"https://registry.npmjs.org/{name}" if registry == "npm" else f"https://pypi.org/pypi/{name}/json"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=4) as r:
            ok = r.status == 200
    except urllib.error.HTTPError as e:
        ok = False if e.code == 404 else None
    except Exception:
        ok = None
    _cache[key] = ok
    return ok


_SEP = r"[\s'\"\[\],()]"
NPM_RE = re.compile(rf"\b(?:npm|i|yarn|pnpm)(?:{_SEP}+add|{_SEP}+install|{_SEP}+i){_SEP}+([^&|;]+)|\bnpx{_SEP}+-?y?{_SEP}+(@?[\w@/.-]+)")
PY_RE = re.compile(rf"\b(?:pip3?|uv)(?:{_SEP}+pip)?{_SEP}+install{_SEP}+([^&|;\]]+)|\buv{_SEP}+add{_SEP}+([^&|;\]]+)")
_PKG = re.compile(r"(?<![\w./-])(@?[\w][\w.-]*)(?:@[><=!~^]?[\w.]+)?")


def _check_packages(command: str) -> str | None:
    targets: list[tuple[str, str]] = []
    m = NPM_RE.search(command)
    if m:
        scope = m.group(1) or m.group(2) or ""
        if m.group(2):  # bare npx package
            targets.append(("npm", m.group(2)))
        else:
            for raw in scope.split():
                p = _PKG.match(raw.strip("\"'-,"))
                if p and not raw.startswith("-"):
                    targets.append(("npm", p.group(1)))
    m = PY_RE.search(command)
    if m:
        scope = m.group(1) or m.group(2) or ""
        for raw in scope.split():
            p = _PKG.match(raw.strip("\"',"))
            if p and not raw.startswith("-"):
                base = re.split(r"[\[=<>!~;]", p.group(1))[0]
                if base:
                    targets.append(("pypi", base))
    for registry, name in targets:
        name = name.rstrip("/")
        if name.startswith(("-", ".")) or "@" in name[1:] and registry == "pypi":
            continue
        if re.fullmatch(r"\d+(&\d*)?", name) or not re.fullmatch(r"[A-Za-z0-9_.@/-]+", name):
            continue  # redirect/shell fragments, not package names
        if len(name) > 64:
            continue  # sentence fragments from multi-line command strings
        ok = _pkg_exists(registry, name)
        if ok is False:
            return name
    return None


def gate(tool_name: str, args: dict, **kwargs):
    """pre_tool_call hook. Returns a block directive or None to pass."""
    try:
        command = " ".join(_strings(args)) if tool_name in ("terminal", "execute_code", "browser_exec") else ""
        if tool_name in ("terminal", "execute_code", "browser_exec") and command.strip():
            bad = _check_packages(command)
            if bad:
                _log(f"BLOCK install tool={tool_name} pkg={bad!r} cmd={command[:160]!r}")
                return {"action": "block", "message": (
                    f"SLOPGUARD blocked this install — package {bad!r} does not exist in "
                    f"its registry. Hallucinated packages are a real attack vector "
                    f"(slopsquatting). Check the spelling or the actual package name, "
                    f"then retry.")}

        if tool_name in ("write_file", "patch"):
            p = _path_of(args)
            if p and _ENV_PATH.search(p):
                return None  # env/credential files are the correct home for keys
            blob = "\n".join(_strings(args))
            for pat, reason in SECRET_PATTERNS:
                hit = pat.search(blob)
                if hit and not _PLACEHOLDER.search(hit.group(0)):
                    _log(f"BLOCK secret tool={tool_name} rule={reason!r} path={p!r}")
                    return {"action": "block", "message": (
                        f"SLOPGUARD blocked this write — {reason} in plaintext "
                        f"({p or 'code content'}). Move it to an environment file "
                        f"(~/.hermes/.env or the project .env) and reference it by name.")}
    except Exception as e:  # never break the agent on a guard bug
        _log(f"ERROR fail-open tool={tool_name}: {e!r}")
    return None


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", gate)
