#!/usr/bin/env python3
"""health/status-server.py — agent-fleet web host on 127.0.0.1:8003 (behind harness.jitinnair.com).

Routes:
  /                      STORE UI (catalog/www/index.html)            — public
  /app.css /app.js /fonts/*   store static assets                    — public
  /api/inventory.json    catalog data (catalog/inventory.json)       — public
  /install.sh, /install.sh.sha256                                    — public
  /status                plain colour status page                    — basic auth
  /status.json           machine-readable status + node reports      — basic auth
  /logs?n=300            log dump (health events + node reports)     — basic auth

Config: ~/.config/agent-fleet/health.env (STATUS_USER, STATUS_PASS; optional HEALTH_DIR,
WWW_DIR). The catalog + store dirs are derived from this file's location.
"""
import base64
import gzip
import json
import mimetypes
import os
import textwrap
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOME = Path(os.path.expanduser("~"))
CONF = Path(os.environ.get("AF_CONF", HOME / ".config/agent-fleet/health.env"))
CFG = {}
if CONF.exists():
    for line in CONF.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            CFG[k.strip()] = os.path.expanduser(os.path.expandvars(v.strip()))
HEALTH_DIR = Path(CFG.get("HEALTH_DIR", HOME / "agent-fleet-health"))
WWW_DIR = Path(CFG.get("WWW_DIR", HOME / "scratch/agent-fleet-www"))
REPO_DIR = Path(__file__).resolve().parent.parent
CATALOG_DIR = REPO_DIR / "catalog"
STORE_DIR = CATALOG_DIR / "www"
USER = CFG.get("STATUS_USER", "admin")
PASS = CFG.get("STATUS_PASS", "")
COLORS = {"green": "#34d399", "yellow": "#fbbf24", "red": "#f87171"}
PUBLIC_FILES = {"/install.sh": WWW_DIR / "install.sh", "/install.sh.sha256": WWW_DIR / "install.sh.sha256"}
STORE_MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
              ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
              ".woff2": "font/woff2", ".json": "application/json"}


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def tail(path: Path, n: int) -> list:
    try:
        return path.read_text(errors="replace").splitlines()[-n:]
    except Exception:
        return []


def node_cards() -> list:
    out = []
    for f in sorted(HEALTH_DIR.glob("node-*.json")):
        d = read_json(f) or {}
        try:
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
            d["age_h"] = round(age.total_seconds() / 3600, 1)
        except Exception:
            d["age_h"] = "?"
        out.append(d)
    return out


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                  .replace('"', "&quot;").replace("'", "&#39;"))


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _short(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return textwrap.shorten(s, width=n, placeholder="…") if len(s) > n else s


def status_page() -> str:
    st = read_json(HEALTH_DIR / "status.json") or {}
    color = st.get("color", "red")
    nodes = node_cards()
    events = "\n".join(esc(l) for l in tail(HEALTH_DIR / "health.log", 25)[::-1])
    node_html = ""
    for nd in nodes:
        age = _num(nd.get("age_h"), default=-1.0)          # -1 = unknown
        dot = COLORS["green"] if not nd.get("behind_origin") and nd.get("conformant") else COLORS["yellow"]
        if age < 0 or age > 8:
            dot = COLORS["red"] if age > 8 else COLORS["yellow"]      # unknown age is amber, not green
        sk = nd.get("skills", {})
        node_html += f"""
        <div class="card"><h2 class="mono eyebrow"><span class="st-dot" style="background:{dot}"></span> node: {esc(nd.get('node','?'))}</h2>
        <table class="st-table">
        <tr><td>reported</td><td>{esc(nd.get('ts','?'))} &nbsp;({esc(nd.get('age_h','?'))} h ago)</td></tr>
        <tr><td>store head</td><td>{esc(nd.get('store_head','?'))} — behind origin: {esc(nd.get('behind_origin','?'))}</td></tr>
        <tr><td>skills</td><td>store {esc(sk.get('store','?'))} · hermes {esc(sk.get('hermes','?'))} · claude {esc(sk.get('claude','?'))} · opencode {esc(sk.get('opencode','?'))} → conformant: <b>{esc(nd.get('conformant','?'))}</b></td></tr>
        <tr><td>update timer</td><td>{esc(nd.get('update_timer','?'))} · last run status {esc(nd.get('last_update_status','?'))}</td></tr>
        <tr><td>disk free</td><td>{esc(nd.get('disk_avail','?'))}</td></tr>
        </table></div>"""
    if not nodes:
        node_html = '<div class="card"><h2 class="mono eyebrow">nodes</h2><p>none reporting yet</p></div>'
    badge = (f'<span class="chip chip-ok">{esc(str(color).upper())}</span>' if color == "green"
             else f'<span class="chip" style="color: var(--{"warn" if color != "red" else "bad"})">{esc(str(color).upper())}</span>')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-fleet status</title>
<meta name="theme-color" content="#0a0a0f">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230a0a0f'/%3E%3Cpath d='M9 21l4.6-11h2.2L20.4 21h-2.3l-1.1-2.8h-4.6L11.3 21H9zm4.1-4.6h3.2l-1.6-4.1-1.6 4.1z' fill='%2322d3ee'/%3E%3Ccircle cx='23.5' cy='20.5' r='1.6' fill='%2334d399'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/app.css"></head><body>
<h1 class="it-title">agent-fleet store — status</h1>
<p class="mono muted">master: kurama-core · updated {esc(st.get('ts','?'))} · <a href="/">store</a> · <a href="/logs">log dump</a> · <a href="/status.json">status.json</a></p>
<p>{badge} <span class="mono muted">issues: {esc(st.get('issues','?'))}</span></p>
<div class="card"><h2 class="mono eyebrow">desktop master</h2><table class="st-table">
<tr><td>store head</td><td>{esc(st.get('head','?'))} (origin {esc(st.get('origin_main','?'))})</td></tr>
<tr><td>skills</td><td>{esc(st.get('skills','?'))}</td></tr>
<tr><td>last sync</td><td>{esc(st.get('sync_age_h','?'))} h ago</td></tr>
<tr><td>uncommitted</td><td>{esc(st.get('dirty_files','?'))} file(s)</td></tr>
<tr><td>telegram</td><td>{esc(st.get('telegram','?'))}</td></tr>
<tr><td>nodes seen</td><td>{esc(st.get('nodes','none'))}</td></tr>
</table></div>
{node_html}
<div class="card"><h2 class="mono eyebrow">recent events</h2><pre class="st-log">{events}</pre></div>
<button class="btn mono" id="st-reload" type="button">Refresh now</button>
<span class="mono muted" id="st-age"></span>
<script>
var loaded = Date.now();
setInterval(function () {{
  var s = Math.round((Date.now() - loaded) / 1000);
  document.getElementById('st-age').textContent = 'page ' + s + 's old';
  if (s >= 60 && (document.visibilityState === 'hidden' || !document.hasFocus())) location.reload();
}}, 5000);
document.getElementById('st-reload').addEventListener('click', function () {{ location.reload(); }});
</script>
</body></html>"""


# ---------- item detail pages ---------------------------------------------------
import sys as _sys
_sys.path.insert(0, str(CATALOG_DIR))
try:
    import md as mdrender  # catalog/md.py — safe markdown -> html
except Exception:
    mdrender = None

PLURALS = {"skill": "skills", "skills": "skills", "mcp": "mcps", "mcps": "mcps",
           "plugin": "plugins", "plugins": "plugins", "tool": "tools", "tools": "tools", "custom": "custom"}


def inv_data():
    return read_json(CATALOG_DIR / "inventory.json") or {}


def find_item(plural, slug):
    for it in inv_data().get(plural) or []:
        if it.get("slug") == slug or it.get("name") == slug:
            return it
    return None


def custom_page_data(slug):
    for c in inv_data().get("custom") or []:
        if c.get("slug") == slug:
            f = REPO_DIR / c.get("path", "")
            body = f.read_text() if f.exists() else ""
            if body.startswith("---"):
                end = body.find("\n---", 3)
                body = body[end + 4:] if end != -1 else body
            return c, body
    return None, ""


def docs_data(repo):
    return read_json(CATALOG_DIR / "docs" / (repo.replace("/", "__") + ".json"))


def render_detail(title, kind, meta, body_md, repo, branch):
    up = meta.get("upstream") or {}
    links = []
    if up.get("repo"):
        stats = f'{up.get("stars")}★ · pushed {str(up.get("pushed_at") or "")[:10]}'
        if up.get("latest_tag"):
            stats += f' · latest {up["latest_tag"]}'
        if up.get("checked_at"):
            stats += f' · checked {up["checked_at"]}'
        links.append(f'<a href="{esc(up["url"])}" target="_blank" rel="noopener noreferrer">↗ {esc(up["repo"])}</a> <span class="stars">{esc(stats)}</span>'
                     + (' <span class="chip">auto-derived</span>' if up.get("derived") else ""))
    if meta.get("homepage"):
        links.append(f'<a class="up-link" href="{esc(meta["homepage"])}" target="_blank" rel="noopener noreferrer">↗ homepage</a>')
    if meta.get("site"):
        links.append(f'<a class="up-link" href="{esc(meta["site"])}" target="_blank" rel="noopener noreferrer">↗ {esc(meta["site"])}</a>')
    if meta.get("repo"):
        links.append(f'<a class="up-link" href="https://github.com/{esc(meta["repo"])}" target="_blank" rel="noopener noreferrer">↗ {esc(meta["repo"])}</a>')

    facts = []
    for k in ("category", "type", "kind", "version", "author", "license", "source", "files",
              "updated", "path", "harnesses", "env", "notes"):
        v = meta.get(k)
        if v:
            facts.append(f'<span class="it-fact"><i>{esc(k)}</i> {esc(", ".join(map(str, v)) if isinstance(v, list) else v)}</span>')
    install = meta.get("install") or ""
    copy_block = ""
    if install:
        copy_block = ('<div class="install it-install"><p class="mono eyebrow">install / connect</p>'
                      f'<code class="mono install-cmd">{esc(install)}</code>'
                      f'<button class="btn btn-ghost mono" data-copy="{esc(install)}" type="button">Copy</button>'
                      '<span class="sr-only" id="copy-status" role="status" aria-live="polite"></span></div>')

    full_summary = (meta.get("description") or meta.get("summary")
                    or meta.get("notes") or "")
    dm = docs_data(repo) if repo else None
    if body_md:
        renderer = mdrender.render if mdrender else (lambda m, repo="", branch="main": f"<p>{esc(_short(m, 500))}</p>")
        html_docs = renderer(body_md, repo=repo or up.get("repo") or "", branch=branch or "main")
        source_line = ""
        if repo:
            source_line = f'official documentation from {esc(repo)} ({esc((dm or {}).get("path") or "README")})'
            if dm and dm.get("fetched_at"):
                source_line += f' · fetched {esc(dm["fetched_at"])}'
        elif meta.get("kind") in ("skill pack", "plugin", "mcp server", "custom"):
            source_line = "maintained in this fleet"
        docs_html = (f'<section class="doc-wrap"><p class="mono muted">{source_line}</p>'
                     f'{mdrender.toc(html_docs) if mdrender else ""}'
                     f'<article class="doc">{html_docs}</article></section>')
    else:
        docs_html = ('<section class="doc-wrap"><p class="mono muted">No public upstream to mirror — this item lives in the '
                     'fleet store itself. Install or update it with the store one-liner above.</p></section>')

    links_html = f'<p class="row it-links">{" ".join(links)}</p>' if links else ""
    facts_html = f'<p class="it-facts">{" ".join(facts)}</p>' if facts else ""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — Agent Fleet Store</title>
<meta name="description" content="{esc(_short(full_summary, 160))}">
<meta name="theme-color" content="#0a0a0f">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230a0a0f'/%3E%3Cpath d='M9 21l4.6-11h2.2L20.4 21h-2.3l-1.1-2.8h-4.6L11.3 21H9zm4.1-4.6h3.2l-1.6-4.1-1.6 4.1z' fill='%2322d3ee'/%3E%3Ccircle cx='23.5' cy='20.5' r='1.6' fill='%2334d399'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/app.css"></head>
<body class="item-body">
<a class="skip" href="#main">Skip to content</a>
<main class="it-wrap" id="main" tabindex="-1">
  <p class="it-top"><a class="it-back mono" href="/">← Agent Fleet Store</a><span class="chip">{esc(kind)}</span></p>
  <h1 class="it-title">{esc(title)}</h1>
  <p class="it-summary" title="{esc(full_summary)}">{esc(full_summary)}</p>
  {links_html}
  {facts_html}
  {copy_block}
  {docs_html}
</main>
<script>
document.querySelectorAll('[data-copy]').forEach(function (b) {{
  b.addEventListener('click', function () {{
    var status = document.getElementById('copy-status');
    function done(ok) {{
      b.textContent = ok ? 'copied' : 'copy failed';
      if (status) status.textContent = ok ? 'Copied to clipboard' : 'Copy failed';
      setTimeout(function () {{ b.textContent = 'Copy'; }}, 1500);
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(b.dataset.copy).then(function () {{ done(true); }}, function () {{ done(false); }});
    }} else {{
      done(false);
    }}
  }});
}});
</script>
</body></html>"""


def item_page(plural, slug):
    if plural == "custom":
        c, body = custom_page_data(slug)
        if not c:
            return None
        return render_detail(c.get("title", slug), c.get("kind", "custom"), c, body, "", "main")
    it = find_item(plural, slug)
    if not it:
        return None
    body, repo, branch = "", "", "main"
    if it.get("custom"):
        _, body = custom_page_data(it["custom"])
    elif (it.get("upstream") or {}).get("repo"):
        d = docs_data(it["upstream"]["repo"])
        if d:
            body, repo, branch = d.get("md") or "", d.get("repo") or "", d.get("branch") or "main"
    return render_detail(it.get("name", slug), plural[:-1], it, body, repo, branch)


_GZ_CACHE = {}
_GZ_TYPES = ("text/html", "text/css", "application/javascript", "application/json", "image/svg+xml")


class H(BaseHTTPRequestHandler):
    server_version = "af-store/2.0"

    def _auth(self) -> bool:
        hdr = self.headers.get("Authorization", "")
        if not PASS:
            return True
        if hdr.startswith("Basic "):
            try:
                u, _, p = base64.b64decode(hdr[6:]).decode().partition(":")
                if u == USER and p == PASS:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="agent-fleet"')
        self.end_headers()
        return False

    def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store"):
        enc = None
        if (len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", "")
                and ctype.split(";")[0] in _GZ_TYPES):
            key = (ctype, hash(body))
            if key not in _GZ_CACHE:
                if len(_GZ_CACHE) > 24:
                    _GZ_CACHE.clear()
                _GZ_CACHE[key] = gzip.compress(body, 6)
            body, enc = _GZ_CACHE[key], "gzip"
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        if enc:
            self.send_header("Content-Encoding", enc)
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _store_file(self, rel: str, cache="max-age=300"):
        f = (STORE_DIR / rel.lstrip("/")).resolve()
        if STORE_DIR.resolve() not in f.parents and f != STORE_DIR.resolve():
            self._send(403, b"denied\n", "text/plain"); return
        if not f.is_file():
            self._send(404, b"not found\n", "text/plain"); return
        ct = STORE_MIME.get(f.suffix) or mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        self._send(200, f.read_bytes(), ct, cache)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        path = u.path

        # ---- public: installer ------------------------------------------------
        if path in PUBLIC_FILES:
            f = PUBLIC_FILES[path]
            if f.exists():
                self._send(200, f.read_bytes(), "text/plain; charset=utf-8")
            else:
                self._send(404, b"missing\n", "text/plain")
            return

        # ---- public: store UI + assets + API -----------------------------------
        if path in ("/", "/index.html"):
            idx = STORE_DIR / "index.html"
            if idx.exists():
                self._send(200, idx.read_bytes(), "text/html; charset=utf-8", "max-age=60")
            else:
                self._send(503, b"store UI not built yet\n", "text/plain")
            return
        if path.startswith("/fonts/"):
            self._store_file(path, cache="max-age=31536000, immutable")
            return
        base = path.split("?", 1)[0]
        if base in ("/app.css", "/app.js") or base in ("/favicon.svg", "/favicon.ico"):
            self._store_file(path)
            return
        if path == "/api/inventory.json":
            inv = CATALOG_DIR / "inventory.json"
            if inv.exists():
                self._send(200, inv.read_bytes(), "application/json", "max-age=120")
            else:
                self._send(503, b"{}\n", "application/json")
            return

        # ---- public: item detail pages + item API ------------------------------
        if path.startswith("/api/item.json"):
            q = parse_qs(u.query)
            plural = PLURALS.get((q.get("kind", ["skills"])[0] or "skills").lower(), "skills")
            slug = (q.get("slug", [""])[0] or "").lower()
            if plural == "custom":
                c, body = custom_page_data(slug)
                if not c:
                    self._send(404, b"{}", "application/json"); return
                self._send(200, json.dumps({"custom": c, "md": body}).encode(), "application/json"); return
            it = find_item(plural, slug)
            if not it:
                self._send(404, b"{}", "application/json"); return
            payload = {"item": it}
            if it.get("custom"):
                c, body = custom_page_data(it["custom"])
                payload["custom"], payload["md"] = c, body
            elif (it.get("upstream") or {}).get("repo"):
                d = docs_data(it["upstream"]["repo"])
                if d:
                    payload["docs"] = {"repo": d.get("repo"), "path": d.get("path"),
                                       "fetched_at": d.get("fetched_at"), "md": d.get("md")}
            self._send(200, json.dumps(payload).encode(), "application/json"); return

        if path.startswith("/item/"):
            parts = path.strip("/").split("/")
            plural = PLURALS.get(parts[1].lower()) if len(parts) == 3 else None
            htmlp = item_page(plural, parts[2].lower()) if plural else None
            if htmlp:
                self._send(200, htmlp.encode(), "text/html; charset=utf-8", "max-age=120")
            else:
                self._send(404, b"not found\n", "text/plain")
            return

        # ---- everything below is admin -----------------------------------------
        if not self._auth():
            return
        if path == "/status":
            self._send(200, status_page().encode(), "text/html; charset=utf-8")
        elif path == "/status.json":
            self._send(200, json.dumps({"desktop": read_json(HEALTH_DIR / "status.json"), "nodes": node_cards()}, indent=2).encode(), "application/json")
        elif path == "/logs":
            n = min(int(parse_qs(u.query).get("n", ["300"])[0] or 300), 2000)
            parts = ["# health.log (last %d)" % n]
            parts += tail(HEALTH_DIR / "health.log", n)
            for f in sorted(HEALTH_DIR.glob("node-*.json")):
                parts += ["", "# latest report: %s" % f.name]
                parts += json.dumps(read_json(f) or {}, indent=2).splitlines()
            self._send(200, ("\n".join(parts) + "\n").encode(), "text/plain; charset=utf-8")
        else:
            self._send(404, b"not found\n", "text/plain")

    def log_message(self, format, *args):  # noqa: A002
        pass


if __name__ == "__main__":
    assert esc('a"b\'c<&>') == 'a&quot;b&#39;c&lt;&amp;&gt;', "esc must cover both quote forms"
    assert _num('?') == 0.0 and _num(None) == 0.0 and _num('3.5') == 3.5, "_num must fall back on bad input"
    ThreadingHTTPServer(("127.0.0.1", 8003), H).serve_forever()
