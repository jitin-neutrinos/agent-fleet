# Print / HTML-to-PDF render traps (WeasyPrint class)

Print output is a render surface like any other: CSS silently misbehaves, and the
only reliable detector is GEOMETRY measured out of the built artifact — never a
visual impression of the HTML source.

Applies to any HTML->PDF pipeline driven by WeasyPrint or headless Chromium.
Renderer-specific details verified against WeasyPrint 70.

## Verify the artifact, not the stylesheet

A stylesheet that looks correct can render wrong in ways no source review finds.
Measure the built PDF:

```bash
pdfinfo out.pdf | grep -Ei '^pages|page size'      # page count + real page box
pdffonts out.pdf                                    # fonts actually embedded
pdffonts out.pdf | tail -n +3 | awk '{print $1}'    # subset names; unstyled
                                                   # fallback faces = your
                                                   # @font-face rules did not match
pdftotext out.pdf - | wc -c                         # text layer exists + size
pdftotext -f N -l N -layout out.pdf -               # per-page text, to read
                                                   # running headers/footers
pdffonts / pdfimages -list                          # per-font and per-image detail
```

`pdfimages -list` gives **x-ppi / y-ppi per page** — the fastest way to catch an
image rendered at the wrong scale on ONE page of a many-page document.

Do NOT conclude a PDF is broken because a generic file reader failed to extract
its text. Cross-check with two independent extractors (`pdftotext` and `pypdf`)
before treating extraction as a defect: a "needs OCR" error from one reader says
nothing about the other.

### Measure image geometry, not just presence

`pdfimages -list` only proves an image is EMBEDDED. To prove it is not
DISTORTED, measure the drawn box and compare its aspect ratio to the source:

```python
import pymupdf
d = pymupdf.open("out.pdf")
for pno, p in enumerate(d):
    for im in p.get_images(full=True):
        for r in p.get_image_rects(im[0]):
            print(f"p{pno+1}: {r.width:.1f} x {r.height:.1f} pt  ratio={r.width/r.height:.3f}")
```

Assert `drawn_ratio == source_ratio` to three decimals. Equal ratios on EVERY
page that carries the asset is the proof the bug is gone; "it looks right now" is
not.

## `attr()` in page margin boxes crashes WeasyPrint

`content: attr(data-section)` inside an `@page` margin box raises
`AttributeError: 'NoneType' object has no attribute 'get'` when the referenced
attribute is absent on some element. Use `string-set` instead, which WeasyPrint
handles reliably:

```css
.s-01{ string-set: section "01 · The case"; }
@page{ @top-right{ content: string(section); font: 400 7.5pt "Poppins"; } }
```

## `body { string-set }` resets the running header on EVERY page

The single most-repeated bug in a section-aware-header build. A `string-set` on
`body` re-asserts on every page, so the header shows the body's value forever and
the per-section rules never appear. Symptom: every page header reads
"Contents" (or whatever the body default was).

**Never put `string-set` on `body`/`html`.** Declare one rule per section and
apply the class to the section's own heading or divider element.

Corollary: when running headers look wrong, verify per PAGE before assuming the
feature is missing — a `string-set` set on a divider legitimately carries across
until the next one, so "page N shows the previous section's title" is correct
behaviour, not a bug.

## Flexbox cross-axis stretch silently overrides image width

An `<img>` sized with `height:` only inside a `display:flex` container (column or
row) gets its **width overridden** by the default `align-items: stretch`, and
grows vertically without bound. The cover page renders fine while the back cover
— same image, flex wrapper — renders ~4x too tall.

```css
/* BROKEN: width is stretched, height grows */
.back{ display:flex; flex-direction:column; }
.back .logo{ height:13mm; }

/* FIX: stop the stretch, and pin both dimensions */
.back{ display:flex; flex-direction:column; align-items:flex-start; }
.back .logo{ flex:0 0 auto; width:60mm; height:auto; }
```

Give every image inside a flex container an EXPLICIT width and `height:auto`.
Height-only sizing works only in normal block flow, which is why the identical
markup on a non-flex wrapper looks perfect and hides the bug.

Detect it by comparing the SAME asset's rendered ratio across pages — one flex
page and one block page differing is the signature.

## Orphaned headings and page-flow audit

```bash
for p in $(seq 3 $(( $(pdfinfo out.pdf | awk '/^Pages/{print $2}') - 2 )) ); do
  pdftotext -f "$p" -l "$p" -layout out.pdf - | sed '/^\s*$/d' | tail -1
done
```

The last line of each page should be body prose, never a heading alone. Apply
`break-after:avoid` to all headings and `break-inside:avoid` to tables, callouts,
diagrams and steps. A heading stranded at a page foot is the defect this catches.

## Monochrome / single-hue brand palettes

When the owner restricts a document to ONE brand hue, derive the whole ramp from
that hue's hex and audit the SOURCE rather than trusting the render:

```bash
grep -oE '#[0-9A-Fa-f]{6}' doc.html | sort | uniq -c | sort -rn
grep -oiE '\b(celeste|mint|salmon|iris|green|orange|purple|teal|cyan)\b' doc.html
```

Every hex must be the base hue, its dark/light steps, white/midnight, or one
declared neutral for body text. Also replace accents hidden in artwork — inline
SVG `stroke`/`fill` values and gradient stops — not just CSS, then confirm zero
matching tokens remain in the file.

## Iteration discipline

- Anchor every surgical edit with an assertion (`assert src.count(old) == 1`) so
  a changed anchor fails loudly instead of silently no-op'ing.
- Render, measure, diff against the previous build, THEN ship. A changed
  `pdfimages`/`pdffonts` row is the regression signal a re-read of the HTML
  cannot give you.
- Watch for the fallback-face tell: unexpected families in `pdffonts` (DejaVu,
  Noto where only Poppins was declared) mean an `@font-face` weight/style axis did
  not match, so the browser silently substituted.
- When the owner says a visual detail is wrong, trust the report as a symptom and
  MEASURE to find the layer — as with the stretched logo, the source looked
  correct on both pages and only per-page geometry revealed which wrapper was at
  fault.
