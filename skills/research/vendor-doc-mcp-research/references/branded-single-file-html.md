# Branded Self-Contained HTML: single-file deliverables with embedded brand assets

Session-tested 2026-09-05: revamped a 52 KB plain-styled HTML doc into a
~0.98 MB fully self-contained Neutrinos-branded page that renders correctly
offline from `file://` with zero external files. Use whenever a brand skill
ships real assets (fonts, logos, tokens) and the deliverable must be ONE
portable file — emailed, moved between machines, or opened without an
`assets/` folder beside it.

## The pattern

1. Locate the brand skill's assets dir on the host (via a bind mount, e.g.
   `~/Work/coding-harness/config/skills/neutrinos-brand-core/assets/`):
   `tokens.css`, `fonts/*.ttf`, `logo/*.png`, `references/*.md`.
2. Read the SKILL.md + design-system reference BEFORE styling. Do not invent
   layout language; the brand defines surface rhythm, devices, and rules.
3. Base64-embed the real assets (never approximate):
   - 4 Poppins weights (300/400/500/600, ~150 KB each TTF) as `@font-face`
     with `data:font/ttf;base64,...` — covers body/regular/headline/semibold.
   - Logo files per surface: horizontal color (light surfaces),
     horizontal color-ondark (midnight footer), symbol color (favicon).
   - Inline `tokens.css` contents (the `:root` vars + `.neu-*` helpers)
     verbatim into `<style>` — do NOT re-type hex values from memory.
4. Build via f-string assembly; total ≈ 910 KB base64 → ~0.95 MB file.

```python
import base64
def datauri(name, mime):
    return f"data:{mime};base64,{b64[name]}"
def fontface(weight, name):
    return (f'@font-face {{ font-family: "Poppins"; font-weight: {weight}; '
            f'font-style: normal; font-display: swap; '
            f'src: url("{datauri(name,"font/ttf")}") format("truetype"); }}')
```

## Reuse prior content, don't rewrite it

Extract body sections from the previous version by their HTML comment markers
into a dict, restyle per section (old heading patterns → new pill+title
pattern, legacy class names → new CSS), then wrap in the new shell. Keep every
`id` (anchors, `rN` citation entries) intact so the citation graph survives.

## "Use the logo accent only" — verify from pixels, not memory

Pure-stdlib PNG color count (no Pillow): inflate IDAT, undo PNG filters
(0–4), tally opaque pixels. On `neutrinos-symbol-color.png` this returns
exactly `#0066FF` — the claim "the accent is the logo blue" becomes evidence.
Then strip every OTHER brand accent from the CSS — including defaults hidden
in tokens.css helpers (`.neu-tag` ships Celeste background,
`.neu-btn--accent` Celeste). Verify with `css.count('celeste') == 0` etc.

## Brand system vs. generic slop tells

When a brand skill exists it OVERRIDES generic anti-slop heuristics:

- "Colored left strip on cards" is a slop tell generically, but in Neutrinos
  the left-edge accent rule IS a brand device (Frame Brackets). Keep it.
- Conic-gradient (donut chart) and radial dot-patterns (momentum swirl) are
  brand devices, not "aggressive gradients". The meaningful check is
  `linear-gradient` count = 0, not "no gradients".
- Headlines only black / brand blue / white — grep-able via the
  `--neu-heading` var being used on all heading rules.

## Honest verification boundary

Structural checks (tag balance via stdlib `html.parser`, anchor graph,
citation graph, accent-count greps) verify the FILE; they do not verify the
RENDER. If no browser/screenshot path is available — and attempting to install
one (playwright chromium, system deps) requires approvals you don't have —
say exactly that and hand over the one-line open command. Never claim visual
verification. See `references/verification.md` for the structural pass and
host-path delivery (bind mounts).

## Pitfall: citation renumbering by regex can silently eat attributes

When tightening the reference list (closing gaps like 1–16 + 19–42 → 1–40),
a remap like `re.sub(r'href="#r(\d+)"', lambda m: f'#r{n-2}', src)` replaces
the WHOLE match — including the `href="` literal — with just `#r17`, producing
`<a class="cite" #r17>[17]</a>`. The file still parses, anchors from the `id=`
side still match, and the damage is invisible until you grep. Two rules:

1. Remap with the attribute preserved:
   `lambda m: f'href="#r{int(m.group(1))-2}"'` — or simpler, don't renumber
   at all (append-only; gaps in the numbering are harmless).
2. After ANY citation renumber, grep for the mangled form before verifying:
   `re.findall(r'<a class="cite" #r\d+>', src)` must be empty, and the
   display-bracket text must stay in sync with its href:
   `[(a,b) for a,b in re.findall(r'href="#r(\d+)" >\[(\d+)\]', src) if a!=b]`.
   Renumbering shifts BOTH the `href`/`id` and the visible `[n]` text — fix
   the display brackets in the same pass or citations point at the wrong
   entries.
