# Bundled Assets Manifest

Everything you need to produce pixel-accurate Neutrinos media is bundled inside
the `neutrinos-brand-core` skill's `assets/` directory. Reference these real files
rather than approximating logos, fonts, or icons.

```
assets/
  tokens.css          CSS custom properties (--neu-*) + @font-face + helper classes
  tokens.json         machine-readable color/type/logo tokens (any language)
  logo/               logo art (see references/logo.md for the full table)
    neutrinos-accepted-logo-styles.svg   vector artboard sheet (ALL lockups at once) -
                                         reference source only; never place directly
    neutrinos-horizontal-*.png           horizontal lockups (color/black/white, +/- tagline)
    neutrinos-vertical-*.png             vertical lockups (color/white/black)
    neutrinos-symbol-*.png               symbol only (color/black/white)
  fonts/              Poppins TTFs (Open Font License - safe to embed/redistribute)
    Poppins-Light.ttf  Poppins-Regular.ttf  Poppins-Medium.ttf
    Poppins-SemiBold.ttf  Poppins-LightItalic.ttf  Poppins-SemiBoldItalic.ttf
  icons/              official icon library (thin line + one solid accent)
    on-light/blue  on-light/green  on-dark/blue  on-dark/green   (~63 icons each)
```

## How to reference assets from a build

**Path contract.** Within a skill, paths are relative to that skill's own root
(`assets/logo/...`, `references/colors.md`). Across skills, all Neutrinos skills
are always siblings, so reference brand-core assets as
`../neutrinos-brand-core/assets/...`, e.g.
`../neutrinos-brand-core/assets/logo/neutrinos-horizontal-color.png`. Never use a
`skills/` prefix and never a harness-specific variable such as
`${CLAUDE_PLUGIN_ROOT}`.
When generating a standalone deliverable for the user, **copy** the assets you use
into the output folder (e.g. `./assets/`) so the deliverable is self-contained.

**Fonts.**
- HTML/print: use the `@font-face` blocks in `tokens.css` (point `url()` at your
  copied `fonts/`), or embed base64 for fully self-contained files.
- WeasyPrint / wkhtmltopdf: install Poppins or point CSS `@font-face` at the TTFs.
- DOCX/PPTX: set the font to "Poppins" (falls back to Segoe UI on Windows).

**Logo.**
- Place a specific PNG lockup from `logo/`; pick the version matching the
  background (see `references/logo.md`).
- `logo/neutrinos-accepted-logo-styles.svg` is an Illustrator artboard sheet showing
  every accepted lockup at once - it is the vector source of truth, not a
  placeable asset. Never embed it as "the logo".
- Per-lockup SVGs can be generated from the sheet with `tools/split_logo_svg.py` in the repo.

**Icons.** Pick one folder (background + single accent) and use icons from it only.

## Licensing notes

- **Poppins** - Open Font License; free to embed and redistribute. Bundled.
- **Segoe UI** - Microsoft system font (Windows). **Not bundled / not
  redistributed;** referenced as a fallback only.
- **Logo & icons** - Neutrinos proprietary brand assets, for Neutrinos work.
- **Photography** - not bundled; must be licensed before use (see
  `references/photography-and-icons.md`).
