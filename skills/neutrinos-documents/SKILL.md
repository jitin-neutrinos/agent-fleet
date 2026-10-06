---
name: neutrinos-documents
description: >-
  Create long-form on-brand Neutrinos documents - handbooks, playbooks, guides,
  manuals, job aids, SOPs, whitepapers, reports - as branded multi-page PDFs
  (or DOCX when editable). Use for any Neutrinos handbook, guide, manual,
  runbook, playbook, report, or structured multi-section document. Handles
  covers, headers/footers, dividers, tables, callouts. Read neutrinos-brand-core
  first; render with neutrinos-print's html_to_pdf.py.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md). PDF rendering needs Python with WeasyPrint or headless Chromium.
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Documents (Handbooks, Guides & Job Aids)

Turn structured content into clean, professional, on-brand documents: a strong
cover, calm typographic pages with real open space, consistent section dividers,
and branded callouts, tables, and footers.

**Always read `neutrinos-brand-core` first.** For PDF rendering, reuse
`neutrinos-print/scripts/html_to_pdf.py`. Research/gather the actual content
before building (don't invent policies, numbers, or steps).

## Pick the format

- **Branded PDF (default)** for handbooks, guides, job aids, reports - fixed,
  polished, on-brand. Build in HTML/CSS -> render with `html_to_pdf.py`.
- **DOCX** when the user must edit it in Word/Google Docs afterward. Read the
  `docx` skill for mechanics; set font to **Poppins** (Segoe UI fallback), apply
  the palette, and keep the layout rules below. Reserve heavy graphic devices for
  the cover.
- **One-page job aid / cheat sheet** - a single dense but open A4 page; see the
  quick-reference pattern below.

## Document anatomy

1. **Cover** - Midnight Blue or Neutrinos Blue field, big Poppins-Medium title,
   short subtitle, the white logo, and a subtle momentum swirl or supergraphic
   bleeding off a corner. Add version/date in small type.
2. **Contents** (for anything > ~6 pages) - Poppins, generous leading, a Celeste
   pill for section numbers.
3. **Section dividers** - a numbered pill + section title on white, echoing the
   Brand Book's own dividers.
4. **Body pages** - one idea per spread; wide margins; running header (doc name /
   section) and footer (page number, "Reinvent. Accelerated." or neutrinos.co).
5. **Callouts / tables / steps** - framed with brackets and the one accent.
6. **Back cover** - logo + tagline, contact, confidentiality line if needed.

## Page CSS scaffold

```css
@page {
  size: A4;
  margin: 22mm 20mm 20mm;
  @top-left    { content: "Neutrinos Employee Handbook"; font: 400 8pt "Poppins"; color:#4A4A4A; }
  @top-right   { content: "Section 2 - Ways of Working";  font: 400 8pt "Poppins"; color:#4A4A4A; }
  @bottom-right{ content: counter(page);                  font: 400 8pt "Poppins"; color:#4A4A4A; }
}
@page cover { margin: 0; }               /* full-bleed cover */
h1{font:500 34pt/1.1 "Poppins";color:#000;letter-spacing:-.01em}
h2{font:500 22pt/1.15 "Poppins";color:#0066FF;margin-top:14pt}
h3{font:600 13pt/1.3 "Poppins";color:#000}
p,li{font:300 10.5pt/1.6 "Poppins";color:#000}
```

## Branded components for documents

- **Section pill:** `<span class="neu-tag">3</span>` before a section title.
- **Callout box:** left frame-bracket rule in the one accent; Mist Gray fill;
  SemiBold label + Light body. Use for tips, notes, warnings (vary by accent but
  keep one accent per page).
- **Steps / job-aid rows:** numbered pills down the left, action in Poppins
  SemiBold, detail in Light. Great for runbooks and how-to guides.
- **Tables:** thin Mist Gray (`#4A4A4A`) rules, Poppins SemiBold header row on Mist Gray (or a
  Neutrinos Blue header with white text), Light body. No heavy borders.
- **Do/Don't grid:** two columns; use Mint for "do", Salmon for "don't" - one of
  the rare places two accents are OK because it is data-like differentiation; keep
  it clean.

## Layout rules (documents)

- **Open space and calm.** Documents are read, not skimmed - give text room, keep
  line length ~60-80 characters, use white and mist gray, save blue/midnight for
  covers and dividers.
- **Headings** black or Neutrinos Blue; body black; never accent-colored headings.
- **Consistency** beats decoration: same margins, same divider style, same footer
  on every page.
- **One accent per page.** Callouts and highlights share the page's single accent.
- **Logo** on cover and back only (small mark in the footer is fine); don't repeat
  the full logo on every page.

## Job aid / quick-reference pattern (one page)

A single A4: title bar (blue) with the task name; a 2-3 column grid of numbered
steps or shortcuts; a small "remember" callout; footer with logo + neutrinos.co.
Dense but breathable - it should be scannable at arm's length.

## Rendering

```bash
# run from the neutrinos-documents directory (all Neutrinos skills are siblings)
python ../neutrinos-print/scripts/html_to_pdf.py handbook.html handbook.pdf
```

The script locates the bundled fonts itself via its own path; `--fonts` is only
needed if you copied assets elsewhere.

Multi-page content flows automatically across `@page`. Verify page breaks (avoid
orphan headings: `h1,h2,h3{break-after:avoid}`), the running header/footer, and
the cover, then run the brand-core Quick Brand Check.