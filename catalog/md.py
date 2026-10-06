#!/usr/bin/env python3
"""catalog/md.py — small, safe Markdown -> HTML renderer for upstream docs.

Conservative by design: all text is HTML-escaped, no raw HTML passthrough, relative
links/images are rewritten against the source repo/branch. Covers the constructs
READMEs actually use: headings, paragraphs, fenced code, lists, tables, quotes, hr,
inline code/bold/italic/strike, links and images. Stdlib only.
"""
import html
import re

_ESC = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _inline(text: str, repo: str, branch: str) -> str:
    t = text.translate(_ESC)
    # code spans first (protect their content from other rules)
    spans = []

    def stash(m):
        spans.append(m.group(1))
        return f"\x00{len(spans) - 1}\x00"

    t = re.sub(r"`([^`]+)`", stash, t)
    # images ![alt](src)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)",
               lambda m: f'<img src="{html.escape(_abs(m.group(2), repo, branch, image=True))}" alt="{m.group(1)}" loading="lazy">', t)
    # links [text](href)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)",
               lambda m: f'<a href="{html.escape(_abs(m.group(2), repo, branch))}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>', t)
    # bold, italic, strike
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", t)
    # bare urls
    t = re.sub(r"(?<![\"'=])(https?://[^\s<>\"]+)",
               lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>', t)
    # restore code spans
    for i, s in enumerate(spans):
        t = t.replace(f"\x00{i}\x00", f"<code>{s}</code>")
    return t


def _abs(url: str, repo: str, branch: str, image: bool = False) -> str:
    if re.match(r"^(https?:|mailto:|#)", url):
        return url
    url = url.lstrip("./")
    kind = "raw" if image else "blob"
    return f"https://github.com/{repo}/{kind}/{branch}/{url}"


def _slug(text, seen):
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-") or "s"
    seen[s] = seen.get(s, 0) + 1
    return s if seen[s] == 1 else f"{s}-{seen[s]}"


def toc(rendered_html: str) -> str:
    heads = re.findall(r'<h([23]) id="([^"]+)">(.*?)<a class="h-anchor"', rendered_html, re.S)
    if len(heads) < 4:
        return ""
    items = "".join(
        f'<li class="toc-l{lvl}"><a href="#{hid}">{re.sub(r"<[^>]+>", "", txt)}</a></li>'
        for lvl, hid, txt in heads)
    return f'<nav class="doc-toc" aria-label="On this page"><p class="mono eyebrow">on this page</p><ul>{items}</ul></nav>'


def render(md: str, repo: str = "", branch: str = "main") -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    out, i, lines = [], 0, md.split("\n")
    n = len(lines)
    seen = {}

    def is_table_sep(s):
        return bool(re.match(r"^\s*\|?\s*:?-{2,}.*\|", s)) or bool(re.match(r"^\s*\|?(\s*:?-{2,}\s*\|)+\s*$", s))

    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            lang = s[3:].strip().split()[0] if s[3:].strip() else ""
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = min(len(m.group(1)) + 1, 6)  # shift down one level under the page title
            hid = _slug(m.group(2).strip(), seen)
            out.append(f'<h{lvl} id="{html.escape(hid)}">{_inline(m.group(2).strip(), repo, branch)}'
                       f'<a class="h-anchor" href="#{html.escape(hid)}" aria-label="Link to this section">#</a></h{lvl}>')
            i += 1
            continue

        if re.match(r"^\s*([-*_])\s*\1\s*\1[\s\S]*$", s) and len(set(s)) <= 2:
            out.append("<hr>"); i += 1; continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf), repo, branch)}</blockquote>")
            continue

        if re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < n and re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", lines[i]).strip())
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x, repo, branch)}</li>" for x in items) + f"</{tag}>")
            continue

        if "|" in line and i + 1 < n and is_table_sep(lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            thead = "".join(f"<th>{_inline(c, repo, branch)}</th>" for c in head)
            tbody = "".join("<tr>" + "".join(f"<td>{_inline(c, repo, branch)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="tbl-scroll"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue

        if not s:
            i += 1
            continue

        # paragraph: consume until blank / block starter
        buf = [s]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|>|\s*([-*+]|\d+[.)])\s|```)", lines[i]):
            if "|" in lines[i] and i + 1 < n and is_table_sep(lines[i + 1]):
                break
            buf.append(lines[i].strip()); i += 1
        out.append(f"<p>{_inline(' '.join(buf), repo, branch)}</p>")

    return "\n".join(out)


if __name__ == "__main__":  # smoke test
    sample = "# Title\n\nHello **bold** `code` [link](docs/x.md) ![i](img/a.png)\n\n- a\n- b\n\n```bash\necho hi\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n> quote\n"
    h = render(sample, repo="o/r", branch="main")
    assert '<h2 id="title">' in h and toc(h) == ""
    assert "<strong>bold</strong>" in h and "<code>code</code>" in h
    assert 'href="https://github.com/o/r/blob/main/docs/x.md"' in h
    assert 'src="https://github.com/o/r/raw/main/img/a.png"' in h
    assert "<ul><li>a</li><li>b</li></ul>" in h
    assert "<pre><code" in h and '<div class="tbl-scroll"><table>' in h and "<blockquote>" in h
    assert "<script" not in render("<script>alert(1)</script>", "o/r")
    print("md.py smoke test ok")
