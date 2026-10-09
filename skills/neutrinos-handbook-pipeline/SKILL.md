---
name: neutrinos-handbook-pipeline
description: >-
  End-to-end pipeline for long-form Neutrinos branded PDF handbooks: research
  with citations, branded HTML from brand-core tokens, venv-isolated
  WeasyPrint render, and verification. Use when building a Neutrinos handbook,
  multi-section branded report, or any long branded PDF that needs the proven
  render-verify loop. Read neutrinos-brand-core first.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md). PDF rendering needs WeasyPrint in a venv (see steps).
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Branded PDF Handbook Pipeline

Field-proven on a 33-page branded handbook. Use for long branded PDFs where
the extra verification loop is worth it; for one-off print pieces,
`neutrinos-print` alone is enough.

## Pipeline

1. **Research:** gather product facts from authoritative sources and cite
   reference URLs; use web search/extract for market evidence. Cite every claim.
2. **Build HTML** with the brand-core tokens (Poppins; `#0066FF`/`#00053D`/
   `#F5F5F5`; one accent per layout, Celeste `#00DEEF`). Reference bundled
   fonts/logos via `../neutrinos-brand-core/assets/` (see the brand-core path
   contract).
3. **Render in an isolated venv** - never the system interpreter:
   `uv venv <scratch>/venv && <scratch>/venv/bin/pip install weasyprint`, then
   `../neutrinos-print/scripts/html_to_pdf.py handbook.html handbook.pdf
   --fonts ../neutrinos-brand-core/assets/fonts`. The script can also set this
   up itself with `--allow-install` (venv at `~/.cache/neutrinos-designer/venv`).
   CHECK FOR THE SHARED VENV FIRST: reuse `~/.cache/neutrinos-designer/venv`
   (`<venv>/bin/python -c "import weasyprint"`) before creating a new one.
4. **Deliver** the PDF through the host's file/media channel (copy to
   `~/uploads/<name>.pdf` for the chat MEDIA tag).

## Design rules (hard requirements)

- Premium, modern, elegant; generous whitespace.
- All content inside page margins. Use **named @page masters** (`content`,
  `bare`) so running headers/footers never bleed onto full-bleed cover/divider/
  back pages.
- Decorative rules sit **below** display numerals, never crossing them.
- Text on dark graphics/panels must be **white or near-white**; dark text only
  on white. All text >= 4.5:1 WCAG AA vs its actual background - audit every
  fg/bg pair.
- Verify referenced asset files exist before rendering - a wrong logo path
  renders silently blank (no error from WeasyPrint).
- After every revision, re-verify: page count (pdfinfo), footers present per
  page class, numeral/rule geometry and logo visibility via pixel analysis.

## Pitfalls

- **An `img` with only a height stretches — give every logo/img both dimensions.**
  `height:11mm` with no width lets the engine's default sizing stretch a ~3:1 horizontal
  lockup into a square; the defect is invisible in the HTML and obvious on the rendered
  cover/back. Always add `width` (sized to the file's real aspect ratio) plus
  `object-fit:contain` — `object-fit` alone is not honored for the implicit width.
- **A single-hue document is a grep, not a render check.** The owner's recurring brief
  is "only the brand blue, dark and light, no other colors". Accents slip back in through
  CSS defaults (callout colors, warn/success hues, accent pills) and survive a visual
  glance on small renders. Grep the built HTML for every non-blue accent hex before
  rendering, and replace them with derived blue tints (`#9FC7FF`, `#BBD4FF`, `#E5F0FF`
  on dark, `#0066FF` on light). Verify with a rendered-page pixel pass when vision is
  available, `pdftotext` + grep when it is not.

- **The HTML lives in scratch, not next to the skills — relative asset paths
  break.** From a scratch dir, `../neutrinos-brand-core/assets/` resolves to
  nothing and the logo/fonts render silently blank. Fix: symlink the skills
  dir into the scratch dir (`ln -sfn ~/.hermes/skills <dir>/skills-link`) and
  rewrite asset URLs to that prefix before rendering; pass the fonts dir
  explicitly via `--fonts` (the script's own path still finds its defaults).
- **WeasyPrint not on the system python is expected, not a failure.**
  `python3 -c "import weasyprint"` failing on PATH means 'wrong interpreter',
  never 'unavailable' — the pipeline's own venv carries it (see step 3).
- **Bare npm style assets (radial-gradient divs, not images) count as
  supergraphics** and satisfy the momentum-graphic rule without any bundled
  asset dependency.
- WeasyPrint paint order: an absolutely-positioned panel can bury a sibling
  logo image; fix with explicit `z-index`.
- Margin-box content can clip at page edges; center boxes and keep bottom
  margin >= 24mm.
- `mask-image` support is partial; don't rely on masks for text-critical
  separation.
- Run `tools/selfcheck.py` after any change to the render stack.

## Mermaid diagrams inside the PDF

Field-proven on the 33-page branded handbook and the 25-page Conduct Evidence Engine
v5 report (9 diagrams). Every item below cost a debug cycle.

**Render mermaid to PNG, never SVG.** WeasyPrint silently drops `foreignObject`
content, and mermaid puts node labels there by default — a 10-label diagram loses 8
of them with no error at all. `"htmlLabels": false` in the mermaid config file does
**not** reach the CLI. PNG embeds perfectly and keeps Poppins exactly as Chromium
draws it.

**Narrow the diagram, do not raise the font.** Print legibility is
`pt = 11.25 * print_mm * 96 / (css_px * 25.4)`, so for a 172 mm portrait column a
diagram wider than ~900 CSS px falls below 8 pt. A 2000 px-wide flowchart prints at
3-6 pt — unreadable in print. Raising the font does not help, because the box grows
with the text. The fix is fewer nodes per rank (3 is the practical max) and shorter
labels. Measure with that formula before embedding, not after.

**Install once, then reuse:**

```
cd <scratch>/mmd && npm install mermaid @mermaid-js/mermaid-cli
cp ~/.hermes/skills/neutrinos-brand-core/assets/fonts/Poppins-*.ttf ~/.local/share/fonts/ && fc-cache -f
```

Poppins must be in the system font path or Chromium falls back to a default sans and
the diagrams stop matching the document.

**Working invocation** (flags verified against `mmdc --help`; `-w`/`--width` do not
exist and fail with "unknown option"):

```
npx mmdc -i fig.mmd -o fig.png --size 900 --scale 3 -b white -p pptr.json -c theme.json
```

- `pptr.json` must be a real JSON file — passing `/dev/null` throws a JSON parse
  error. Shape:
  `{"args":["--no-sandbox","--disable-setuid-sandbox"],"executablePath":"<playwright chromium>","fontFamily":"Poppins"}`
- Chromium path on this host:
  `~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome` — note
  `chrome-linux64`, not `chrome-linux`.
- `theme.json` needs `theme: "base"` plus a `themeVariables` block built from the
  brand hexes, or the diagram renders in mermaid's default multi-colour palette and
  breaks the one-accent rule. `classDef` per node kind still overrides the theme.

**Do not nest double quotes inside a node label.** `T1["Body: { \"input\": ... }"]`
fails with `Parse error ... got 'STR'`. Reword the label and put the literal JSON in
a `<pre>` block in the document body instead.

**Split long flows.** A 12-step vertical flowchart is unusable at any legible font
size. Cut it into 4a/4b halves, lay each out left-to-right with a `subgraph` per
phase, and it becomes two wide banners that sit above their prose. Verify with
`vision_analyze` on a ~100 dpi page render — that is the only check that catches both
clipping and unreadable type.
