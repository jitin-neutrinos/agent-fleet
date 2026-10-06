---
name: neutrinos-print
description: >-
  Design and produce print-ready Neutrinos media as PDF - brochures, flyers,
  posters, one-pagers, sales sheets, business cards, letterhead, banners. Use
  for any Neutrinos brochure, flyer, poster, business card, letterhead, or
  "something to print" / "printable PDF" in the brand. Builds HTML/CSS for
  paper and renders via bundled html_to_pdf.py. Read neutrinos-brand-core
  first.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md). PDF rendering needs Python with WeasyPrint or headless Chromium.
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Print Media

Produce print-ready PDFs that hold the brand precisely: dominant white/blue,
Poppins, real open space, the correct logo with clear space, and one accent.

**Always read `neutrinos-brand-core` first.** Then design in HTML/CSS sized for
paper and render with `scripts/html_to_pdf.py`.

## Why HTML -> PDF

HTML/CSS gives pixel control, easy use of `tokens.css`, real Poppins, and crisp
vector logo (SVG) - then WeasyPrint renders a print-ready PDF. This is more
reliable and on-brand than drawing PDFs by hand, and far better than office
templates for fixed layouts.

## Workflow

1. Read `neutrinos-brand-core` (`colors.md`, `typography.md`, `logo.md`,
   `design-system.md`).
2. Copy the assets you need next to your HTML: `tokens.css`, `fonts/`, the logo
   file(s), any icons. Keep the deliverable self-contained.
3. Set the **page size and margins** in CSS `@page` (see sizes below). Add bleed
   if it goes to a commercial printer.
4. Lay out with brand patterns: bold Poppins-Medium headline, short body in a
   frame bracket, one brand graphic (supergraphic/momentum/photo), generous margins.
5. Render: `python scripts/html_to_pdf.py input.html output.pdf`.
6. Open the PDF, eyeball it against the brand-core Quick Brand Check, iterate.

## Page setup

Use `@page` for size, margins, and (for commercial print) bleed:

```css
@page { size: A4 portrait; margin: 18mm; }          /* letterhead, one-pager */
/* Business card (with 3mm bleed): size 91mm x 55mm; content inside 3mm safe margin */
/* US Letter: size: 8.5in 11in;  Poster: size: A3/A2;  Trifold: size: A4 landscape */
```

Common pieces and sizes:

| Piece | Size | Notes |
| --- | --- | --- |
| Business card | 3.5 x 2 in (89 x 51 mm) or 91 x 55 mm w/ bleed | Heavy cover stock, matte/silk. Front: horizontal logo + contact (Poppins Medium name); back: blue field, symbol, tagline. Build contact block up from the bottom. |
| Letterhead | A4 / US Letter | Bright-white smooth stock. Logo top-left; screened symbol watermark lower-right; address line footer. |
| Envelope | DL / #10 | Logo + return address top-left. |
| One-pager / product sheet | A4 / US Letter | Product logo top-left; blue accent column of icons+features; screenshot; blue headline; footer logo + neutrinos.co. |
| Brochure (trifold) | A4 landscape, 3 panels | Cover panel: bold statement + supergraphic; inner panels alternate white/mist-gray. |
| Flyer | A4 / A5 | Single bold message, one graphic, one CTA. |
| Poster | A3 / A2 / A1 | Huge headline, supergraphic or momentum swirl, minimal copy. |

## Print-specific rules

- **Color:** dominant white + Neutrinos Blue; Mist Gray / Midnight Blue support;
  one accent. Provide values in CMYK when the printer needs them (see `colors.md`).
- **Type:** Poppins embedded (WeasyPrint reads the bundled TTFs via `@font-face`);
  Medium headlines, SemiBold sub-heads, Light body. Upper-and-lowercase.
- **Logo:** use the transparent PNGs (`../neutrinos-brand-core/assets/logo/...`)
  or a single-lockup SVG produced from the vector sheet; keep >= 1/4 X clear
  space; respect min size (25px/10px equivalents scale up fine in print). The
  bundled the bundled artboard sheet `../neutrinos-brand-core/assets/logo/neutrinos-accepted-logo-styles.svg` is an artboard sheet of all
  lockups - never place it directly.
- **Bleed & safety:** for commercial print add 3mm bleed and keep text within a
  safe margin; supergraphics/photos that touch the edge should bleed.
- **Images:** 300 DPI for print. The bundled logo SVG is resolution-independent.
- **Paper guidance to pass along:** business cards - heavy cover, matte/silk;
  letterhead/envelope - high-quality bright-white smooth stock; print on a
  high-quality professional digital printer.

## Rendering with the bundled script

`scripts/html_to_pdf.py` renders HTML to PDF using WeasyPrint and registers the
bundled Poppins fonts automatically.

```bash
# auto-detects an existing weasyprint; never installs into the system Python
python scripts/html_to_pdf.py brochure.html brochure.pdf
# optional: point at the bundled fonts explicitly
python scripts/html_to_pdf.py brochure.html brochure.pdf --fonts ../neutrinos-brand-core/assets/fonts
```

If WeasyPrint is unavailable in the environment, fall back to headless Chromium
(`playwright`/`chromium --headless --print-to-pdf`) with `@page` CSS; the same
HTML works. The script prints guidance if it can't render.

## Business-card starter (front)

```html
<!doctype html><html><head><meta charset="utf-8">
<style>
  @page { size: 89mm 51mm; margin: 0; }
  @font-face{font-family:"Poppins";font-weight:500;src:url("./fonts/Poppins-Medium.ttf")}
  @font-face{font-family:"Poppins";font-weight:400;src:url("./fonts/Poppins-Regular.ttf")}
  body{margin:0;font-family:"Poppins";color:#000}
  .card{width:89mm;height:51mm;box-sizing:border-box;padding:6mm;display:flex;flex-direction:column;justify-content:space-between}
  img{height:9mm}
  .name{font-weight:500;font-size:9pt;margin:0}
  .meta{font-size:7pt;line-height:1.5;color:#000;margin:1mm 0 0}
</style></head>
<body><div class="card">
  <img src="./logo/neutrinos-horizontal-color.png" alt="Neutrinos">
  <div>
    <p class="name">Laila Kumar</p>
    <p class="meta">Project Manager<br>No. 9, 14th Main Road, Sarjapura Road<br>
    HSR Layout Sector 5, Bengaluru - 560 034<br>+91 965 581 4047 &nbsp; laila.kumar@neutrinos.co</p>
  </div>
</div></body></html>
```