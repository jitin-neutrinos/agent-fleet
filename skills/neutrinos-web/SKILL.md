---
name: neutrinos-web
description: >-
  Build on-brand Neutrinos websites, landing pages, web apps, dashboards, and
  application UIs in HTML/CSS/JS or React. Use for any Neutrinos web page,
  hero, microsite, signup flow, dashboard, or "build/design a page or site for
  Neutrinos". Read neutrinos-brand-core first for tokens and rules; this skill
  covers web build mechanics.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md).
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Web & Apps

Build websites and app UIs that look unmistakably Neutrinos: white and blue
dominant, Poppins, bold headlines, real open space, one accent for energy.

**Always read `neutrinos-brand-core` first** (colors, typography, logo, design
system). Inline or link `../neutrinos-brand-core/assets/tokens.css` so every value is exact. If a
`modern-web-guidance` skill is available, consult it for current CSS/HTML best
practices - brand rules from here sit on top of that.

## Workflow

1. Load `neutrinos-brand-core`; read `../neutrinos-brand-core/references/design-system.md` and `colors.md`.
2. Decide the surface rhythm: alternate **White**, **Mist Gray**, **Neutrinos
   Blue**, and **Midnight Blue** sections. White + blue dominate; blue/midnight
   sections are punctuation, not the whole page.
3. Bring in `tokens.css` (variables + `.neu-*` helpers). Load Poppins (bundled
   `@font-face` or Google Fonts; see `../neutrinos-brand-core/references/typography.md`).
4. Build sections with bold Poppins-Medium headlines, short body, one accent, and
   a single brand graphic each (supergraphic, momentum swirl, frame bracket, or
   photo).
5. Place the correct logo version in the header/footer with full clear space.
6. Run the brand-core Quick Brand Check and a responsive/accessibility pass.

## Layout patterns that read as Neutrinos

- **Hero:** dark (Midnight Blue) or blue field on one side, a screened **momentum
  swirl** bleeding off the opposite corner, a big white/blue headline, one short
  paragraph in a **frame bracket**, and a **pill** CTA button. Leave real space.
- **Alternating sections:** white -> mist gray -> midnight blue -> white. Keep each
  section to one idea.
- **Feature cards:** square or lightly-rounded white cards on mist gray, thin
  frame-bracket accent, a library icon (one accent), Poppins-SemiBold sub-head.
- **Logo cloud / social proof:** grayscale partner logos on white with lots of gap.
- **Footer:** Midnight Blue, white logo, Poppins-Light links, "Reinvent. Accelerated."

## Signature components (from tokens.css)

- **Pill tag** `.neu-tag` - the rounded eyebrow/section label (often Celeste Blue).
- **Buttons** `.neu-btn`, `.neu-btn--ghost`, `.neu-btn--accent` - fully rounded pills.
- **Frame bracket** `.neu-frame` - left-edge accent rule; extend to angled corners
  for heroes.
- **Dark section** `.neu-dark` - flips a section to Midnight Blue + white text.

## Do / Don't (web-specific)

**Do**
- Keep massive open space; resist filling every column.
- Headlines black or Neutrinos Blue on light, white on dark. One accent per view.
- Use `../neutrinos-brand-core/assets/logo/neutrinos-horizontal-color.png` (or the
  version matching your background) in the header; `neutrinos-symbol-color.png` from `../neutrinos-brand-core/assets/logo/`
  for the favicon. The only bundled SVG is the full artboard sheet - do not place
  it directly.
- Buttons and tags are pills; corners elsewhere are square or lightly rounded.
- Use the momentum swirl / supergraphic **subtly** - background, screened, bleeding.

**Don't**
- Don't recolor headlines with accents or use accents as large background fields.
- Don't crowd sections or use drop shadows on the logo.
- Don't mix two accent colors in one view.
- Don't stretch/rotate the logo or extend its lines in a lockup.

## Starter shell

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Neutrinos</title>
  <link rel="stylesheet" href="./assets/tokens.css">
  <link rel="icon" href="./assets/logo/neutrinos-symbol-color.png">
</head>
<body class="neu neu-body">
  <header>
    <img src="./assets/logo/neutrinos-horizontal-color.png" alt="Neutrinos" height="28">
  </header>

  <section class="neu-dark" style="padding: var(--neu-space-24) var(--neu-space-8)">
    <span class="neu-tag">Reinvent. Accelerated.</span>
    <h1 style="font-size: var(--neu-fs-display); max-width: 14ch; margin: var(--neu-space-6) 0">
      Build agility. Accelerate transformation.</h1>
    <p style="max-width: 46ch; color: var(--neu-text-muted)">
      Neutrinos hyper-accelerates insurers' time to market - without sacrificing flexibility.</p>
    <a class="neu-btn" href="#">Get started</a>
  </section>
</body>
</html>
```

## React / component work

Expose the tokens as JS/theme values (import `tokens.json` or mirror the `--neu-*`
variables). Keep the same rules: Poppins, dominant white/blue, one accent,
open space, pill buttons/tags, bundled logo. For component libraries, set the
theme's `fontFamily`, `colors`, and `radii` from the tokens.

## Publishing

For a durable page the user will revisit or share, persist it as an Artifact (or
via the host's persist flow) - see the host's artifact guidance. Copy any
referenced assets into the output so the page is self-contained; for artifacts
where external files are blocked, inline the CSS and base64-embed the fonts/logo.