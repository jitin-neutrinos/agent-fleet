"""Self-check for slopguard scoped-package name extraction.

Proves the guard no longer false-positives on scoped npm packages with a
version spec (npm registry treats '<name>@<version>' as a 404; '<name>'
returns 200).
"""
import importlib.util
import json
import urllib.request
import urllib.error

spec = importlib.util.spec_from_file_location(
    "sg", "/home/notjitin/.hermes/plugins/slopguard/__init__.py"
)
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)

CASES = [
    # (command, expected extracted name or None-if-token-skipped)
    ("npx -y @mcpware/pagecast@0.2.1 --version", "@mcpware/pagecast"),
    ("npx -y @playwright/mcp@latest --headless", "@playwright/mcp"),
    ("npm i -g typescript", "typescript"),
    ("npm install react@19", "react"),
    ("npm i minimatch", "minimatch"),
    ("pip install playwright", None),  # pypi path, not npm
]


def target_names(cmd: str) -> list[str]:
    """Re-produce the targets list _check_packages builds (names only)."""
    import re as _re

    targets = []
    m = sg.NPM_RE.search(cmd)
    if m:
        scope = m.group(1) or m.group(2) or ""
        if m.group(2):
            targets.append(("npm", sg._npm_base(m.group(2))))
        else:
            for raw in scope.split():
                if raw.startswith("-"):
                    continue
                targets.append(("npm", sg._npm_base(raw)))
    return [n for _, n in targets]


failures = 0
for cmd, expected in CASES:
    if expected is None:
        continue
    names = target_names(cmd)
    ok = expected in names
    print(f"{'PASS' if ok else 'FAIL'}  {cmd!r} -> {names}")
    if not ok:
        failures += 1

# The regression that started this: registry must respond to the base name
URL = "https://registry.npmjs.org/@mcpware/pagecast"
try:
    with urllib.request.urlopen(urllib.request.Request(URL, method="GET"), timeout=5) as r:
        live = r.status == 200
except urllib.error.HTTPError as e:
    live = e.code == 200
print(f"{'PASS' if live else 'FAIL'}  registry 200 for @mcpware/pagecast (base name)")
failures += 0 if live else 1

# Confirms the original bug: name-with-version yields 404 (guard used to hit this URL)
URL_V = "https://registry.npmjs.org/@mcpware/pagecast@0.2.1"
code = None
try:
    with urllib.request.urlopen(urllib.request.Request(URL_V, method="GET"), timeout=5) as r:
        code = r.status
except urllib.error.HTTPError as e:
    code = e.code
print(f"{'PASS' if code == 404 else 'FAIL'}  registry 404 for name@version (original bug shape)")
failures += 0 if code == 404 else 1

print("RESULT:", "all-pass" if failures == 0 else f"{failures} failing")
raise SystemExit(0 if failures == 0 else 1)
