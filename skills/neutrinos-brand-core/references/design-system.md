# Visual Design System

How Neutrinos layouts look and the graphic devices that make them recognizable.

## Design principles

The visual system embodies: **Simplicity, Clean, Modern, Bold, Sophisticated,
Professional, Open-Space.** Bold yet sophisticated; a professional appearance that
communicates confidence and trust. Layouts are characterized by **open space** -
elements are allowed to breathe, creating an uncluttered, inviting experience.

Practical translation:
- **Open space first.** Generous margins and gaps. If it feels crowded, cut content
  or add space - do not shrink the whitespace.
- **Modern, organized, asymmetric.** Off-center compositions, aligned to a clear
  grid. Not centered-and-symmetrical by default.
- **Bold, restrained palette.** Big White/Blue fields, minimal accent.
- **Few elements, high contrast.** One clear focal point per view.

## Layout

Modern, organized, and asymmetric, always with open space. Compose with large
color blocks (White, Neutrinos Blue, Midnight Blue, Mist Gray), a strong headline,
and a supporting block of body text set inside a frame bracket or a card. Let one
side carry the weight and leave the other open.

## Symbol Supergraphic

The Neutrinos symbol used large, as a background/hero graphic. **Use the
established supergraphic art - do not create new art by extending the logo's lines
yourself in a lockup.** For the supergraphic specifically:

- The symbol's angled lines may be extended **indefinitely** on either side; they
  need not be equal, but extend **>= 1X** (X = width of the shorter angled lines on
  the standard symbol).
- It may vary in size and sit anywhere in the layout; it can be full color or
  screened back as a **watermark**.
- When used alongside the logo signature, the supergraphic should be at least
  **400% larger** than the logo (so it never competes with the logo).
- The angled bracket/line motif in Frame Brackets follows this same symbol angle.

## Neutrinos Momentum Graphics

Dynamic elements representing **particles of momentum, energy, agility, and speed**:

- **Circular "swirl"** of dots is the **primary** momentum graphic.
- **Linear "wave"** of dots is the alternative.
- They may be animated individually or transition into each other.
- Use **sparingly**, with minimal surrounding graphic elements.
- Position anywhere; they may vary in size and **bleed off** the layout edge.
- Any approved color combination; the graphic should appear **subtle** against the
  background (often a screened/tonal version of the background color).

## Frame Brackets

Corner/edge rules that **frame typography, photography, and other elements**. The
corner angle **follows the angle in the Neutrinos symbol.** They:

- Provide structure, organization, asymmetry, and a place for a color **accent**.
- May vary within a design; ends can extend **indefinitely** at both ends.
- Are a natural home for the **one** accent color in use.

In `tokens.css`, `.neu-frame` gives a simple left-edge bracket; extend it with
angled corners for hero blocks.

## Charts & graphs

Make charts **simple, bold, and legible.**

- **Color:** Neutrinos **core colors dominate**; accent colors may appear but stay
  **secondary**. All colors can be **screened** to differentiate series. Charts are
  the one place multiple accents may coexist for data differentiation.
- **Type:** Poppins throughout (Segoe UI in Microsoft apps).
- Common forms in the system: donut/percentage rings, vertical bars, stacked bars
  (blue + midnight blue), line charts, and horizontal bars with gray track.
- Keep gridlines light, label directly where possible, avoid 3-D and heavy effects.
- See the `dataviz` guidance if available; apply this palette on top of it.

## Putting a page together (recipe)

1. Choose a dominant surface: White, Mist Gray, Neutrinos Blue, or Midnight Blue.
2. Place a bold Poppins Medium headline (black/blue on light, white on dark).
3. Add one supporting text block in a frame bracket or card - keep it short.
4. Add **one** brand graphic: a supergraphic, a momentum swirl, or a photo.
5. Choose **one** accent (Celeste, Mint, Salmon, or Iris) for a small highlight.
6. Leave a third to half of the composition as open space.
7. Place the correct logo version with full clear space.
