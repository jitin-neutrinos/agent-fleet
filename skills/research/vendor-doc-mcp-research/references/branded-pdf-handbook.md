# Branded Multi-Page PDF Handbook Pipeline

Proven end-to-end on a 26-page A4 handbook (cover, TOC, 8 section dividers,
running headers/footers, tables, callouts, step rows, back cover) rendered
with WeasyPrint and delivered over Telegram. Working example HTML lives only
in that session's scratch — this file captures the reusable pattern.

## Rendering environment (host has no weasyprint)

The host python is externally managed (PEP 668) and usually has no weasyprint.
Build a throwaway venv — never install into system python, which leaves the
user's environment dirty for a document they asked for once:

```bash
cd <scratchdir>
python3 -m venv pdfenv
./pdfenv/bin/pip install weasyprint     # quiet; ~30-60s
```

`uv` is faster but is not always present — plain `venv` + `pip` is the
portable default and works everywhere.

Then render. The bundled renderer resolves the brand fonts from its own
location, so `font-family:"Poppins"` works with no flags:

```bash
./pdfenv/bin/python <skills>/neutrinos-print/scripts/html_to_pdf.py in.html out.pdf
```

**If you pass `--fonts` you are now maintaining font registration yourself.**
The reliable pattern that survives a re-read of the CSS months later is to
declare every weight explicitly in the document itself and point at absolute
paths, so the HTML is self-describing:

```css
@font-face{font-family:"Poppins";src:url("file:///abs/path/Poppins-Light.ttf");font-weight:300}
@font-face{font-family:"Poppins";src:url("file:///abs/path/Poppins-Medium.ttf");font-weight:500}
@font-face{font-family:"Poppins";src:url("file:///abs/path/Poppins-SemiBold.ttf");font-weight:600}
```

Declare every weight you actually use. A missing weight silently falls back
to a system font and the PDF looks subtly wrong in a way page count and
text-layer checks will not catch.

## Asset wiring

Logo files referenced by `<img src="file:///abs/path/logo/...png">` embed
automatically (WeasyPrint resolves local file paths). Use the `file://`
scheme explicitly — a bare absolute path works inconsistently.

Verify embedding rather than assuming it: `pdfimages -list out.pdf` should
show the logo with its dimensions, and a `smask` row confirms the
transparency channel survived. The white-on-dark cover logo needs it.

## Section-aware running headers — use string-set, never attr()

`@page` margin boxes cannot resolve `attr()` in WeasyPrint. Referencing an
attribute absent on some elements throws
`AttributeError: 'NoneType' object has no attribute 'get'` and the render
dies outright rather than degrading.

Give each section a class and set the string literally per class:

```css
.s-01{ string-set: section "01 · The case"; }
.s-02{ string-set: section "02 · Findings"; }
@page{ @top-right{ content: string(section); font:400 7.5pt "Poppins"; color:#4A4A4A; } }
```

Two traps that cost a full render cycle each:

- **A `string-set` on `body` applies on every page and resets the value.**
  You get the same header repeated on all pages while the CSS looks
  correct. Put the initial value on the first section element, never on `body`.
- **`attr()` inside a `string-set` selector silently does nothing.** Even
  where it does not raise, the string never updates. Literal per-class values
  are the only reliable form.

Apply the classes with an asserted replace batch (`assert
src.count(needle)==1`) so a moved anchor fails loudly instead of leaving the
header stale.

## CSS patterns that worked under WeasyPrint

- **Full-bleed cover/back:** a named page — `.cover { page: cover; width:210mm; height:296mm; }`
  and `@page cover { margin:0; background:#00053D; }`. Give the cover div the
  exact page height minus a hair (296mm vs 297mm) to avoid a spurious blank page.
- **Section dividers:** `page-break-before: always` + a full-height `.divider`
  div on a white named page; oversized ghost numeral (`15mm`, `#E4E4E4`)
  behind the title.
- **No flexbox/grid.** Multi-column card rows render as `display:table` /
  `display:table-cell` with `border-spacing` for gutters. Two-column prose
  via `column-count:2` works.
- **Orphan control:** `h3,h4,h5 { page-break-after: avoid; }`,
  `tr, .callout, .steprow { page-break-inside: avoid; }`.
- Decorative radial-gradient circles for the momentum swirl render fine;
  bleeding off-canvas needs `overflow:hidden` on the page-sized wrapper.

## QA gate when vision analysis is unavailable

vision_analyze can be down (provider 429) — don't block on it. The text-layer
gate catches structural breakage:

1. `pdfinfo out.pdf` — page count sane, A4 size, not encrypted.
2. `pdftotext -f 1 -l 3 out.pdf -` — cover title/subtitle and TOC entries
   present and in order.
3. `pdftotext out.pdf - | tail` — back-cover text present (proves last page
   rendered, i.e. no blank-page cascade).
4. `pdffonts out.pdf` — every weight you declared is actually embedded.
   Unlisted brand weights mean a silent system-font fallback.
5. `pdfimages -list out.pdf` — logo present, `smask` row for transparency.
6. Optional: `pdftoppm -png -r 40 -f 1 -l 4 out.pdf qa` — cheap page rasters a
   human can eyeball later or a later vision call can consume.

**Check the running header on several pages, not just page1.** This is the
one check that catches a broken `string-set`, and it is invisible unless you
look:

```bash
for p in 2 7 11 18; do printf "p%-3s " $p; \
  pdftotext -f $p -l $p -layout out.pdf - | head -1 | tr -s ' '; done
```

Each page must show its own section name. Identical text on every page means
the string never updated even though the render succeeded and every other
check passed.

**Scan for orphaned headings** — a heading as the last line of a page with its
body overleaf reads as broken:

```bash
for p in $(seq 3 27); do pdftotext -f $p -l $p -layout out.pdf - \
  | sed '/^\s*$/d' | tail -2 | head -1; done
```

Fix with `break-after: avoid` on the heading and `break-inside: avoid` on the
table/callout that follows it.

If a later vision pass is possible, spot-check cover + one dense body page for
overlap/clipping. Text-layer checks do NOT catch visual collisions — say so
in the delivery message if only the text gate ran.

## Delivery — confirm the surface's working path before emitting

Do not assume `MEDIA:/abs/path` renders on the surface you are replying from.
The marker is parsed by the frontend, but resolution of the path is the
server's job and servers accept a limited set of roots.

Check the frontend's media-path helper for the convention before the first
emit — it usually documents the working root in a comment. For the Astra web
UI the working root is `~/uploads/`, and the `~/` is expanded **server-side**:
the code explicitly notes that stripping the tilde turns `~/uploads/a.png`
into a 404. So copy the artifact into `~/uploads/` and point the marker there
rather than at wherever you happened to build it.

Check the media-kind table too — an extension not listed renders as a plain
link or as "other" instead of an inline card with a viewer.

Write the artifact to a stable path (project deliverable directory) *and* copy
to the delivery root, so the user has a durable copy regardless of which
surface received it.

## Delivery (Telegram)

Write the PDF to a scratch dir and emit `MEDIA:/abs/path/out.pdf` on its own
line in the reply. Well under the 25 MB attachment cap (~260 KB for 26 pages
with embedded fonts). Verify with `file` + `pdfinfo` before claiming done.
