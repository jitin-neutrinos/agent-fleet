#!/usr/bin/env python3
"""catalog/build-inventory.py — scans the agent-fleet store and writes catalog/inventory.json.

Reads:   skills/**/SKILL.md, mcp/*.{list,json}, plugins/**, harness/*.sh, health/*,
         catalog/upstreams.json (curated map), catalog/upstream.json (latest stats, optional),
         ~/.hermes/skills/.hub/lock.json (provenance for hub-installed skills).
Writes:  catalog/inventory.json  (served read-only by health/status-server.py)

Stdlib only. Run after each sync (hook) and daily by agent-fleet-catalog.timer.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

AF = Path(os.environ.get("AF_DIR", Path(__file__).resolve().parent.parent))
CAT = AF / "catalog"
HUB_LOCK = Path.home() / ".hermes/skills/.hub/lock.json"


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def frontmatter(path: Path):
    """Minimal YAML-ish frontmatter reader: top-level scalars + a nested 'metadata' block."""
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return {}, ""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm, body = text[3:end], text[end + 4:]
    data, cur, buf = {}, None, []
    for raw in fm.splitlines():
        if not raw.strip():
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", raw):
            if cur:
                data[cur] = " ".join(buf).strip()
            k, _, v = raw.partition(":")
            cur, buf = k.strip(), [v.strip().lstrip(">|").strip()]
        elif cur and raw.startswith((" ", "\t")):
            s = raw.strip()
            if ":" in s and not s.startswith("-"):
                k, _, v = s.partition(":")
                data[f"{cur}.{k.strip()}"] = v.strip().strip('"').strip("'")
            elif s.startswith("-"):
                buf.append(s.lstrip("- ").strip())
            else:
                buf.append(s)
    if cur:
        data[cur] = " ".join(buf).strip()
    out = {}
    for k, v in data.items():
        if k == "metadata":
            continue
        out[k] = v.strip().strip('"').strip("'")
    return out, body


def first_paragraph(body: str) -> str:
    for block in body.split("\n\n"):
        b = block.strip()
        if b and not b.startswith(("#", "|", "```", ">")):
            return re.sub(r"\s+", " ", re.sub(r"[*_`\[\]]", "", b))[:240]
    return ""


def dir_stats(d: Path):
    files = size = 0
    for root, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if x != ".git"]
        for n in names:
            fp = Path(root) / n
            try:
                size += fp.stat().st_size
                files += 1
            except OSError:
                pass
    return files, size


# ---------- provenance --------------------------------------------------------
provenance = {}
if HUB_LOCK.exists():
    try:
        for name, e in (json.loads(HUB_LOCK.read_text()).get("installed") or {}).items():
            src = e.get("source") or ""
            provenance[name] = {
                "source": {"official": "hermes builtin", "skills.sh": "skills.sh"}.get(src, src or "?"),
                "source_id": e.get("identifier") or "",
                "hash": (e.get("content_hash") or "").replace("sha256:", "")[:12],
                "trust": e.get("trust_level") or "",
            }
    except Exception as ex:
        print(f"[inventory] lock.json unreadable: {ex}", file=sys.stderr)

upstreams = {}
up = CAT / "upstreams.json"
if up.exists():
    upstreams = json.loads(up.read_text())
stats = {}
usp = CAT / "upstream.json"
if usp.exists():
    try:
        stats = (json.loads(usp.read_text()).get("repos") or {})
    except Exception:
        pass


def upstream_view(repo, derived=False):
    s = stats.get(repo) or {}
    v = {"repo": repo, "url": f"https://github.com/{repo}", "stars": s.get("stars"),
         "pushed_at": s.get("pushed_at"), "latest_tag": s.get("latest_tag"),
         "head_sha": s.get("head_sha"), "checked_at": s.get("checked_at")}
    if derived:
        v["derived"] = True
    return v


def attach_upstream(item, mp):
    repo = (mp.get(item["name"]) or {}).get("repo")
    if repo:
        item["upstream"] = upstream_view(repo)


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9._-]+", "-", str(s).lower())).strip("-") or "item"


def derive_repo(path):
    """Best-effort: first real github.com/owner/repo URL in a skill's frontmatter head (auto-provenance)."""
    try:
        head = path.read_text(errors="replace")[:2500]
    except Exception:
        return ""
    m = re.search(r"(?<!gist\.)github\.com/([\w.-]+/[\w.-]+)", head)
    if not m:
        return ""
    repo = re.sub(r"[^A-Za-z0-9._/-].*$", "", m.group(1)).rstrip(".-/").removesuffix(".git")
    if len(repo.split("/")[-1]) < 2:
        return ""
    return repo


STORE_INSTALL = "curl -fsSL https://harness.jitinnair.com/install.sh | bash"
STORE_INSTALL_WIN = "irm https://harness.jitinnair.com/install.ps1 | iex"


def docs_meta(repo):
    """Docs availability for a repo (file written by catalog/docs-worker.py)."""
    f = CAT / "docs" / (repo.replace("/", "__") + ".json")
    try:
        d = json.loads(f.read_text())
        return {"repo": repo, "path": d.get("path"), "fetched_at": d.get("fetched_at")}
    except Exception:
        return None


# ---------- skills ------------------------------------------------------------
skills = []
for sk in sorted(AF.glob("skills/**/SKILL.md")):
    rel = sk.relative_to(AF / "skills")
    parts = rel.parts
    d = sk.parent
    fm, body = frontmatter(sk)
    name = fm.get("name") or (parts[-2] if len(parts) >= 2 else d.name)
    cat = parts[0] if len(parts) >= 2 else "misc"
    files, size = dir_stats(d)
    item = {
        "name": name,
        "category": cat,
        "description": (fm.get("description") or first_paragraph(body))[:240],
        "version": fm.get("metadata.version") or fm.get("version") or "",
        "author": fm.get("metadata.author") or fm.get("author") or "",
        "license": fm.get("license") or "",
        "files": files,
        "size_kb": round(size / 1024),
        "updated": datetime.fromtimestamp(sk.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d"),
        "path": str(d.relative_to(AF)),
        "source": provenance.get(name, {}).get("source", "local"),
        "source_id": provenance.get(name, {}).get("source_id", ""),
        "hash": provenance.get(name, {}).get("hash", ""),
    }
    attach_upstream(item, upstreams.get("skills") or {})
    if not item.get("upstream"):
        dr = derive_repo(sk)
        # keep auto-derived links only when the fetcher could confirm the repo exists
        if dr and not (stats.get(dr) or {}).get("error"):
            item["upstream"] = upstream_view(dr, derived=True)
    item["slug"] = slugify(name)
    item["page"] = "/item/skills/" + item["slug"]
    item["install"] = STORE_INSTALL
    if item.get("upstream"):
        item["docs"] = docs_meta(item["upstream"]["repo"])
    skills.append(item)

# ---------- mcps ----------------------------------------------------------------
def parse_list(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("|")]
        while len(f) < 6:
            f.append("")
        rows.append(f)
    return rows


mcps = {}


def mcp_entry(name):
    return mcps.setdefault(name, {"name": name, "type": "", "target": "", "env": [],
                                  "harnesses": [], "machine_local": False, "notes": ""})


def add_env(entry, keys):
    for k in keys:
        if k and k not in entry["env"]:
            entry["env"].append(k)


for f in parse_list(AF / "mcp/hermes.list"):
    name, kind, spec, args, envs, notes = f[:6]
    # tolerate a legacy row shape where env names sit in the notes column
    if not envs and re.fullmatch(r"[A-Z0-9_,]+", notes or ""):
        envs, notes = notes, ""
    e = mcp_entry(name)
    e["type"] = kind
    if spec.startswith("MACHINE_LOCAL:"):
        e["machine_local"] = True
        e["target"] = spec.split(":", 1)[1] + (" " + args if args else "")
    else:
        e["target"] = (spec + (" " + args if args else "")).strip()
    e["notes"] = e["notes"] or notes
    add_env(e, envs.split(","))
    if "hermes" not in e["harnesses"]:
        e["harnesses"].append("hermes")

for f in parse_list(AF / "mcp/claude.list"):
    name, kind, spec, args, envs, notes = f[:6]
    e = mcp_entry(name)
    e["type"] = e["type"] or kind
    e["target"] = e["target"] or (spec + (" " + args if args else "")).strip()
    e["notes"] = e["notes"] or notes
    add_env(e, envs.split(","))
    if "claude" not in e["harnesses"]:
        e["harnesses"].append("claude")

ocp = AF / "mcp/opencode.json"
if ocp.exists():
    for name, v in json.loads(ocp.read_text()).items():
        e = mcp_entry(name)
        if v.get("type") == "remote":
            e["type"] = e["type"] or "http"
            e["target"] = e["target"] or v.get("url", "")
        else:
            e["type"] = e["type"] or "stdio"
            e["target"] = e["target"] or " ".join(v.get("command", []))
        add_env(e, [m.group(1) for m in re.finditer(r"\{env:([A-Z0-9_]+)\}", json.dumps(v))])
        if "opencode" not in e["harnesses"]:
            e["harnesses"].append("opencode")

gem = AF / "mcp/gemini.json"
if gem.exists():
    for name, v in (json.loads(gem.read_text()).get("mcpServers") or {}).items():
        e = mcp_entry(name)
        if v.get("httpUrl"):
            e["type"] = e["type"] or "http"
            e["target"] = e["target"] or v["httpUrl"]
        else:
            e["type"] = e["type"] or "stdio"
            e["target"] = e["target"] or " ".join([v.get("command", "")] + v.get("args", []))
        add_env(e, [m.group(1) for m in re.finditer(r"\$\{([A-Z0-9_]+)", json.dumps(v))])
        if "gemini" not in e["harnesses"]:
            e["harnesses"].append("gemini")

# antigravity consumes the claude set by design
for name in [x["name"] for x in mcps.values() if "claude" in x["harnesses"]]:
    mcps[name]["harnesses"].append("antigravity")
mcps_list = sorted(mcps.values(), key=lambda x: x["name"])
for e in mcps_list:
    attach_upstream(e, upstreams.get("mcps") or {})
    e["slug"] = slugify(e["name"])
    e["page"] = "/item/mcps/" + e["slug"]
    e["install"] = e["target"]
    if e.get("upstream"):
        e["docs"] = docs_meta(e["upstream"]["repo"])

# ---------- plugins ---------------------------------------------------------------
plugins = []
hpd = AF / "plugins/hermes"
if hpd.exists():
    for p in sorted(hpd.iterdir()):
        y = p / "plugin.yaml"
        if not (p.is_dir() and y.exists()):
            continue
        meta = {}
        for line in y.read_text().splitlines():
            if ":" in line and not line.startswith(" "):
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip().strip('"')
        entry = {"name": meta.get("name", p.name), "kind": "hermes plugin",
                 "version": meta.get("version", ""), "description": meta.get("description", ""),
                 "homepage": meta.get("homepage", ""), "path": str(p.relative_to(AF))}
        attach_upstream(entry, upstreams.get("plugins") or {})
        plugins.append(entry)
mkt = AF / "plugins/marketplace/.claude-plugin/marketplace.json"
if mkt.exists():
    for pl in json.loads(mkt.read_text()).get("plugins", []):
        src = (AF / "plugins/marketplace" / pl.get("source", "").lstrip("./")).resolve()
        ver = ""
        for cand in (src / "plugin.json", src / ".claude-plugin/plugin.json"):
            if cand.exists():
                try:
                    ver = json.loads(cand.read_text()).get("version", "")
                except Exception:
                    pass
                break
        entry = {"name": pl.get("name", "?"), "kind": "claude marketplace",
                 "version": ver, "description": pl.get("description", ""), "homepage": "",
                 "path": str(src.relative_to(AF)) if src.is_dir() else ""}
        attach_upstream(entry, upstreams.get("plugins") or {})
        plugins.append(entry)

# ---------- tools -------------------------------------------------------------------
TOOLS = [
    ("install.sh", "installer", "One-liner installer — detects harnesses, installs skills/plugins/MCP defs on a machine."),
    ("install.ps1", "installer", "Windows one-liner installer (PowerShell 5.1+, no WSL/Git Bash needed) — same fleet, windows-native legs."),
    ("update.sh", "updater", "Consumer-side refresh: pulls the store and mirrors skills into local harnesses."),
    ("sync-from-desktop.sh", "sync", "Desktop source-of-truth push: mirrors ~/.hermes/skills into the repo, commits, pushes, refreshes the site."),
    ("health/fleet-health.sh", "health", "Master health check: sync freshness, site integrity, node reports, Telegram alerts."),
    ("health/node-report.sh", "health", "Node heartbeat: pushes this machine's store state to the master."),
    ("health/status-server.py", "web", "Web server for the store + status + log dump on 127.0.0.1:8003."),
    ("catalog/build-inventory.py", "catalog worker", "Builds catalog/inventory.json from the store (this page's data source)."),
    ("catalog/upstream-worker.py", "catalog worker", "Refreshes upstream repo stats for every connected item (daily)."),
    ("lib/common.sh", "shared lib", "Shared helpers for the installer legs (detection, env keys, manifest)."),
    ("harness/hermes.sh", "harness leg", "Installs into Hermes: skills, plugins, MCP servers (all profiles)."),
    ("harness/claude.sh", "harness leg", "Installs into Claude Code: skills, marketplace plugins, MCP servers."),
    ("harness/opencode.sh", "harness leg", "Installs into OpenCode: skills + MCP config merge."),
    ("harness/gemini.sh", "harness leg", "Installs into Gemini CLI: MCP config merge."),
    ("harness/antigravity.sh", "harness leg", "Installs into Antigravity (agy): skills + MCP servers."),
]
TOOL_CMDS = {
    "install.sh": STORE_INSTALL,
    "install.ps1": STORE_INSTALL_WIN,
    "update.sh": "bash ~/agent-fleet/update.sh",
    "sync-from-desktop.sh": "bash ~/agent-fleet/sync-from-desktop.sh",
    "fleet-health.sh": "bash ~/agent-fleet/health/fleet-health.sh",
    "node-report.sh": "bash ~/agent-fleet/health/node-report.sh",
    "status-server.py": "systemctl --user restart agent-fleet-www.service",
    "build-inventory.py": "python3 ~/agent-fleet/catalog/build-inventory.py",
    "upstream-worker.py": "python3 ~/agent-fleet/catalog/upstream-worker.py",
    "docs-worker.py": "python3 ~/agent-fleet/catalog/docs-worker.py",
}
tools = []
for path, kind, desc in TOOLS:
    name = path.split("/")[-1]
    tools.append({"name": name, "kind": kind, "description": desc, "path": path,
                  "exists": (AF / path).exists(), "slug": slugify(name),
                  "page": "/item/tools/" + slugify(name),
                  "install": TOOL_CMDS.get(name, "")})

for pl in plugins:  # pages + installs for plugins (defined above)
    pl["slug"] = slugify(pl["name"])
    pl["page"] = "/item/plugins/" + pl["slug"]
    pl["install"] = (f"claude plugin install {pl['name']}@agent-fleet"
                     if pl["kind"] == "claude marketplace"
                     else f"hermes plugin: plugins/hermes/{pl['name']} (installed by the store installer)")
    if pl.get("upstream") and pl["upstream"].get("repo") not in (None, "jitin-neutrinos/agent-fleet"):
        pl["docs"] = docs_meta(pl["upstream"]["repo"])

# ---------- custom pages (ours: neutrinos packs, our plugins) -------------------------
now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
custom = []
cdir = CAT / "custom"
if cdir.exists():
    for f in sorted(cdir.glob("*.md")):
        text = f.read_text()
        fm, body = {}, text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                for line in text[3:end].splitlines():
                    if ":" in line and not line.startswith(" "):
                        k, _, v = line.partition(":")
                        fm[k.strip()] = v.strip()
                body = text[end + 4:]
        slug = fm.get("slug") or slugify(f.stem)
        custom.append({"slug": slug, "title": fm.get("title") or slug, "kind": fm.get("kind", "custom"),
                       "summary": fm.get("summary", ""), "repo": fm.get("repo", ""), "site": fm.get("site", ""),
                       "install": fm.get("install", ""), "attach": fm.get("attach", ""),
                       "path": str(f.relative_to(AF))})
        att = fm.get("attach", "")
        if att:
            group, _, iname = att.partition("/")
            bucket = {"skills": skills, "mcps": mcps_list, "plugins": plugins, "tools": tools}.get(group) or []
            for it in bucket:
                if it.get("name") == iname:
                    it["custom"] = slug
                    break

# derived repo list for the workers (zero-maintenance upstream discovery)
derived = sorted({i["upstream"]["repo"] for i in skills + mcps_list + plugins
                  if i.get("upstream") and i["upstream"].get("derived")})
(CAT / "derived-repos.json").write_text(json.dumps({"generated_at": now_iso, "repos": derived}, indent=1))

# ---------- meta + write --------------------------------------------------------------
out = {
    "generated_at": now_iso,
    "head": run("git", "-C", str(AF), "rev-parse", "--short", "HEAD"),
    "branch": run("git", "-C", str(AF), "rev-parse", "--abbrev-ref", "HEAD"),
    "counts": {"skills": len(skills), "mcps": len(mcps_list), "plugins": len(plugins), "tools": len(tools)},
    "categories": sorted({s["category"] for s in skills}),
    "skills": skills, "mcps": mcps_list, "plugins": plugins, "tools": tools, "custom": custom,
}
CAT.mkdir(exist_ok=True)
target = CAT / "inventory.json"
# Only rewrite when the content actually changed (ignore the timestamp) — keeps sync commits meaningful.
# ---------- copy overlay (enriched descriptions) -----------------------------
def apply_copy_overlay(out: dict) -> dict:
    """Overlay reviewed copy from catalog/copy-overrides.json onto catalog items.

    Fields patched per section: skills/plugins/tools -> description, mcps -> notes,
    custom -> summary. Unknown overlay keys are ignored so the file can drift. The
    overlay is applied AFTER the change-detector snapshot so it never re-triggers
    the write path on its own."""
    p = CAT / "copy-overrides.json"
    try:
        ov = json.loads(p.read_text())
    except Exception:
        return out
    fields = {"skills": "description", "mcps": "notes", "plugins": "description",
              "tools": "description", "custom": "summary"}
    n = 0
    for section, field in fields.items():
        patch = ov.get(section) or {}
        for it in out.get(section) or []:
            v = patch.get(it.get("name") or it.get("slug"))
            if v and v != it.get(field):
                it[field] = v
                n += 1
    if n:
        print(f"[inventory] copy overlay applied to {n} items")
    return out

out = apply_copy_overlay(out)

comparable = dict(out, generated_at="")
try:
    old = json.loads(target.read_text())
    if dict(old, generated_at="") == comparable:
        print(f"[inventory] unchanged ({out['counts']}), keeping {target.name}")
        raise SystemExit(0)
except FileNotFoundError:
    pass
except SystemExit:
    raise
except Exception:
    pass
tmp = target.with_suffix(".json.tmp")
tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
tmp.replace(target)
print(f"[inventory] {out['counts']} -> {target} ({target.stat().st_size // 1024} KB), head {out['head']}")
