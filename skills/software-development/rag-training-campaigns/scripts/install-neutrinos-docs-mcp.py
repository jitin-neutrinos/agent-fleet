#!/usr/bin/env python3
"""install-neutrinos-docs-mcp — one-command installer for the Neutrinos Docs MCP.

Detects every AI harness installed on the machine and installs the remote MCP
into each, with an animated branded Neutrinos TUI (pixel-art logo traced from
the official symbol, Neutrinos Blue only).

Usage:
  install-neutrinos-docs-mcp.py [URL]        install (default URL)
  install-neutrinos-docs-mcp.py --remove     remove from all detected harnesses

Customize DEFAULT_URL / NAME below for other MCPs.
"""
import json
import os
import shutil
import subprocess
import sys
import time

BLUE = "\033[38;5;33m"      # Neutrinos Blue #0066FF
BOLD = "\033[1m"
WHITE = "\033[97m"
DIM = "\033[90m"
RESET = "\033[0m"
MIDNIGHT = "\033[38;5;17m"  # Midnight Blue #00053D (brand supporting color)

DEFAULT_URL = "https://mcp.glitchzerolabs.com/mcp"
NAME = "neutrinos-docs"

# Pixel-art traced from the official Neutrinos symbol (bundled brand asset),
# rendered in Neutrinos Blue only.
PIXEL_LOGO = [
    "█       █████                   ████",
    "███     ██████                ██████",
    "█████   ████████            ████████",
    " █████  ██████████         █████████",
    "   ████ ████  █████      ██████  ███",
    "    ███ ████   ██████  ██████   ████",
    "        ████     ██████████     ████",
    "        ████       ███████      ████",
    "        ████ ██     ██████      ████",
    "        ████ ████     ██████    ████",
    "        ████ █████      ██████  ████",
    "        ████  ██████      █████ ████",
    "        ████    ██████     ████ ████",
    "        ████      ██████     ██ ████",
    "        ████      ███████       ████",
    "        ████     ██████████     ████",
    "        ████   ██████  ██████   ████ ███",
    "        ███  ██████      █████  ████ ████",
    "        █████████         ██████████  █████",
    "        ████████            ████████   █████",
    "        ██████                ██████     ███",
    "        ████                   █████       █",
]

SPINNER = "◐◓◑◯"


def c(text, color=BLUE):
    return f"{color}{text}{RESET}"


def banner(url):
    print()
    for line in PIXEL_LOGO:
        print(c("  " + line, BLUE))
    print()
    print(c("  Neutrinos Docs MCP".center(len(PIXEL_LOGO[0]) + 2), BLUE + BOLD))
    print(c("  Reinvent. Accelerated.".center(len(PIXEL_LOGO[0]) + 2), DIM))
    print()
    print(f"  {WHITE}Remote endpoint:{RESET} {WHITE}{url}{RESET}")
    print(f"  {DIM}hybrid retrieval · EmbeddingGemma-300M · 88.8% recall@10{RESET}")
    print()


def spinner_wait(msg, seconds=1.2):
    """Animated spinner while 'working'."""
    n = len(SPINNER)
    steps = max(1, int(seconds / 0.12))
    for i in range(steps):
        s = SPINNER[i % n]
        sys.stdout.write(f"\r  {c(s, BLUE)} {DIM}{msg}{RESET}")
        sys.stdout.flush()
        time.sleep(0.12)
    sys.stdout.write("\r" + " " * (len(msg) + 8) + "\r")
    sys.stdout.flush()


# ------------------------------------------------------------ harness detection & install

def _have(cmd):
    return shutil.which(cmd) is not None


def _json_edit(path, mode, name, url, container="mcpServers", entry=None):
    try:
        cfg = json.load(open(path))
    except Exception:
        return "no config", False
    servers = cfg.setdefault(container, {})
    if mode == "remove":
        existed = servers.pop(name, None) is not None
        status = "removed" if existed else None
    else:
        servers[name] = entry or {"url": url}
        status = "MCP added"
    json.dump(cfg, open(path, "w"), indent=2)
    return status, True


def _yaml_edit(path, mode, name, url, key_hint, entry=None, config_key=""):
    try:
        import yaml
    except ImportError:
        return "yaml missing", False
    try:
        cfg = yaml.safe_load(open(path)) or {}
    except Exception:
        return "no config", False
    key = key_hint
    if config_key:
        found = [k for k in cfg if config_key in k.lower()
                 and isinstance(cfg[k], dict) and cfg[k]]
        key = found[0] if found else key_hint
        cfg.setdefault(key, {})
    servers = cfg.setdefault(key, {})
    if not isinstance(servers, dict):
        servers = cfg[key] = {}
    if mode == "remove":
        existed = servers.pop(name, None) is not None
        status = "removed" if existed else None
    else:
        servers[name] = entry or {"url": url}
        status = "MCP added"
    cfg[key] = servers
    yaml.safe_dump(cfg, open(path, "w"), sort_keys=False)
    return status, True


def h_claude(mode, url):
    label, det = "Claude Code", _have("claude")
    if not det:
        return label, None
    if mode == "remove":
        r = subprocess.run(["claude", "mcp", "remove", NAME], capture_output=True)
        return label, "removed" if r.returncode == 0 else None
    r = subprocess.run(["claude", "mcp", "add", "--transport", "http", NAME, url],
                       capture_output=True)
    return label, "MCP added" if r.returncode == 0 else "failed"


def h_agy(mode, url):
    label, det = "agy (Antigravity)", _have("agy")
    if not det:
        return label, None
    if mode == "remove":
        r = subprocess.run(["agy", "mcp", "remove", NAME], capture_output=True)
        return label, "removed" if r.returncode == 0 else None
    r = subprocess.run(["agy", "mcp", "add", NAME, url], capture_output=True)
    return label, "MCP added" if r.returncode == 0 else "failed"


def h_opencode(mode, url):
    label, det = "opencode", _have("opencode")
    if not det:
        return label, None
    cfg_path = os.path.expanduser("~/.config/opencode/opencode.json")
    if mode == "remove":
        if not os.path.exists(cfg_path):
            return label, None
        status, _ = _json_edit(cfg_path, mode, NAME, url)
        return label, status
    r = subprocess.run(["opencode", "mcp", "add", NAME, "--url", url], capture_output=True)
    return label, "MCP added" if r.returncode == 0 else "failed"


def h_codex(mode, url):
    label, det = "Codex CLI", _have("codex")
    if not det:
        return label, None
    if mode == "remove":
        r = subprocess.run(["codex", "mcp", "remove", NAME], capture_output=True)
        return label, "removed" if r.returncode == 0 else None
    r = subprocess.run(["codex", "mcp", "add", NAME, "--url", url], capture_output=True)
    return label, "MCP added" if r.returncode == 0 else "failed"


def h_gemini(mode, url):
    label, det = "Gemini CLI", _have("gemini")
    if not det:
        return label, None
    if mode == "remove":
        r = subprocess.run(["gemini", "mcp", "remove", NAME], capture_output=True)
        return label, "removed" if r.returncode == 0 else None
    r = subprocess.run(["gemini", "mcp", "add", NAME, "--transport", "http", url],
                       capture_output=True)
    return label, "MCP added" if r.returncode == 0 else "failed"


def h_hermes(mode, url):
    label = "Hermes Agent"
    if not _have("hermes"):
        return label, None
    path = os.path.expanduser("~/.hermes/config.yaml")
    if not os.path.exists(path):
        return label, None
    status, ok = _yaml_edit(path, mode, NAME, url, "mcp_servers", {"url": url},
                            config_key="mcp")
    return label, status if ok else None


def h_cursor(mode, url):
    label = "Cursor"
    cfg = os.path.expanduser("~/.cursor/mcp.json")
    if not os.path.exists(cfg) and not _have("cursor"):
        return label, None
    status, _ = _json_edit(cfg, mode, NAME, url)
    return label, status


def h_windsurf(mode, url):
    label = "Windsurf"
    cfg = os.path.expanduser("~/.codeium/windsurf/mcp_config.json")
    if not os.path.exists(cfg) and not os.path.isdir(os.path.expanduser("~/.codeium")):
        return label, None
    status, _ = _json_edit(cfg, mode, NAME, url)
    return label, status


def h_vscode(mode, url):
    label = "VS Code"
    candidates = [os.path.expanduser("~/.vscode/mcp.json"),
                  os.path.expanduser("~/.config/Code/User/mcp.json")]
    cfg = next((p for p in candidates if os.path.exists(p)), None)
    if cfg is None and not os.path.isdir(os.path.expanduser("~/.vscode")):
        return label, None
    if cfg is None:
        return label, None
    status, _ = _json_edit(cfg, mode, NAME, url, container="servers",
                           entry={"type": "http", "url": url})
    return label, status


def h_generic(mode, url):
    label = "Other (~/.mcp.json)"
    cfg = os.path.expanduser("~/.mcp.json")
    if not os.path.exists(cfg):
        return label, None
    status, _ = _json_edit(cfg, mode, NAME, url)
    return label, status


HARNESSES = [h_claude, h_agy, h_opencode, h_codex, h_gemini,
             h_hermes, h_cursor, h_windsurf, h_vscode, h_generic]


def main():
    url = DEFAULT_URL
    mode = "install"
    args = [a for a in sys.argv[1:]]
    if args and args[0] == "--remove":
        mode = "remove"
        args = args[1:]
    if args:
        url = args[0]

    banner(url)

    # detection phase (animated)
    spinner_wait("Detecting installed AI harnesses…", 1.0)

    verb = "Removing from" if mode == "remove" else "Installing into"
    print(c(f"  {verb} detected harnesses", BLUE + BOLD))
    print(c("  " + "─" * 46, MIDNIGHT))

    added, removed, failed = 0, 0, 0
    for fn in HARNESSES:
        label, status = fn(mode, url)
        if status is None:
            continue  # not installed -> not shown
        spinner_wait(f"{label}…", 0.5)
        if status == "MCP added":
            added += 1
            print(c(f"  ✓ {label:<24}", BLUE) + c("MCP added", WHITE))
        elif status == "removed":
            removed += 1
            print(c(f"  ✓ {label:<24}", BLUE) + c("removed", WHITE))
        else:
            failed += 1
            print(c(f"  ✗ {label:<24}", BLUE) + c(status, DIM))

    print(c("  " + "─" * 46, MIDNIGHT))
    if mode == "remove":
        print(c(f"  {removed} harness(es) cleaned.", WHITE))
    else:
        noun = "harness" if added == 1 else "harnesses"
        print(c(f"  {added} {noun} now carry the MCP.", WHITE))
        print()
        print(f"  {DIM}Restart any running sessions to activate.{RESET}")
        print(f"  {DIM}Tools: search_docs · get_doc_page · list_publications{RESET}")
    print()


if __name__ == "__main__":
    main()
