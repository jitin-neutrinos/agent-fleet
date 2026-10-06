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
4. **Deliver** the PDF through the host's file/media channel.

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

- WeasyPrint paint order: an absolutely-positioned panel can bury a sibling
  logo image; fix with explicit `z-index`.
- Margin-box content can clip at page edges; center boxes and keep bottom
  margin >= 24mm.
- `mask-image` support is partial; don't rely on masks for text-critical
  separation.
- Run `tools/selfcheck.py` after any change to the render stack.
