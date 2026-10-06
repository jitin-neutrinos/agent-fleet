# Verification Recipe: HTML Design Artifacts without a Browser

Session-tested 2026-09-05 on `Neutrinos AI Hub Use Case.html` (a 31 KB,
self-contained doc artifact). Use when browser verification is unavailable —
e.g. the browser daemon needs an interactive Chrome approval popup on a
headless/no-user session, so `browser_exec` cannot open `file://` pages.

## What to run (stdlib `html.parser`, no deps)

A structural pass catches the errors that actually ship in generated HTML:
unbalanced tags, stray closes, `<a>` tags missing `href`, and broken internal
anchor links (`href="#x"` with no `id="x"`). External-link hygiene check: every
`http(s)` href should belong to the domain you claim to cite.

```python
import html.parser, re

class Check(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.errors=[]; self.counts={}
        self.void={'meta','link','br','hr','img','input','area','base',
                   'col','embed','source','track','wbr'}
    def handle_starttag(self,tag,attrs):
        if tag not in self.void: self.stack.append(tag)
        self.counts[tag]=self.counts.get(tag,0)+1
        d=dict(attrs)
        if tag=='a' and 'href' not in d: self.errors.append('<a> without href')
    def handle_endtag(self,tag):
        if tag in self.void: return
        if not self.stack: self.errors.append(f'unmatched </{tag}>'); return
        if self.stack[-1]==tag: self.stack.pop()
        elif tag in self.stack:
            while self.stack and self.stack[-1]!=tag:
                self.errors.append(f'implicit close <{self.stack.pop()}> before </{tag}>')
            self.stack.pop()
        else: self.errors.append(f'stray </{tag}>')

src=open(path).read()
c=Check(); c.feed(src); c.close()
print('unclosed:', c.stack or 'none')
print('errors:', c.errors or 'none')
ids=set(re.findall(r'id="([^"]+)"',src))
missing=set(re.findall(r'href="#([^"]+)"',src))-ids
print('missing anchor targets:', missing or 'none')
ext=re.findall(r'href="(https[^"]+)"',src)
print('external links:', len(ext))
```

Green = `unclosed: none`, `errors: none`, `missing anchor targets: none`.

## Honest reporting

Say exactly what was and was not verified: "HTML parsed clean (no unclosed
tags, all N internal anchors resolve), browser render not exercised." Never
claim the page *renders* — parsing clean is not rendering. Offer the user the
one-line open command instead.

## Delivering to a host desktop from a containerized session

`sandbox /workspace` is NOT a host path. The user hit `ERR_FILE_NOT_FOUND`
opening `/workspace/...html` in their desktop browser. Bind mounts (check
`mount | grep btrfs`) expose host dirs inside the container — e.g.
`/home/notjitin/Work` maps to the host's `~/Work`. Copy the artifact to a
bind-mounted path and give the host-side path in the open command. Verify the
copy with `ls -la` (size must match the source).
