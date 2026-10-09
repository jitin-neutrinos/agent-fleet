---
name: neutrinos-brand-core
description: >-
  Foundational Neutrinos brand system: colors, typography, logo rules, design
  principles, voice. Load FIRST whenever creating, styling, or brand-checking
  anything for Neutrinos - web, print, documents, slides, social, or "make it
  on-brand". Carries exact hex values, Poppins, logo files, fonts, and icon
  library. All media skills build on this; read before them.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md).
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Brand Core

This is the single source of truth for the Neutrinos visual and verbal identity.
Every other Neutrinos skill depends on it. When you are making anything for
Neutrinos, apply these rules; when a media skill (web, print, documents,
presentations, social) is also relevant, read this first, then that skill.

**Who Neutrinos is (one line):** an insurance-focused digital-transformation
company - a MACH, composable, low-code process-automation platform with
pre-built accelerators. Positioning: the *challenger* brand in insurance.
Tagline: **Reinvent. Accelerated.** Narrative line: **Build Agility. Accelerate
Transformation.**

The brand's own words for how it should look and feel: **simple, clean, modern,
bold, sophisticated, professional, and full of open space.** When in doubt,
remove clutter and add breathing room. Bold but never busy.

---

## The five things to get right every time

1. **Color** - White and Neutrinos Blue dominate. One accent, used sparingly.
2. **Typography** - Poppins, upper-and-lowercase. Headlines only in black, blue, or white.
3. **Logo** - Use a bundled file, never redraw it, give it clear space, respect the don'ts.
4. **Open space + asymmetry** - Let elements breathe; modern, organized, off-center layouts.
5. **Voice** - Confident, knowledgeable, human. "Reinvent. Accelerated."

---

## Color (essentials)

Core colors - **White (`#FFFFFF`) and Neutrinos Blue (`#0066FF`) are the two
dominant colors in every communication.** Supporting: Mist Gray (`#F5F5F5`),
Midnight Blue (`#00053D`), Black (`#000000`, body copy).

Accent colors - add energy, never dominate. Use **one at a time** with the core
colors: Celeste Blue `#00DEEF`, Mint Green `#00EFAD`, Salmon `#FB327E`, Iris
`#9A67FB`. **Never combine two accents in one layout** (charts are the only
exception).

**Headlines appear only in Black, Neutrinos Blue, or White** - never an accent.

Full specification (hex/RGB/CMYK/PMS, approved combinations, screening, dark
surfaces, accessibility contrast notes): **read `references/colors.md`.**

The machine-readable values live in **`assets/tokens.json`**; ready-to-use CSS
custom properties and helper classes live in **`assets/tokens.css`** - link or
inline that file rather than re-typing hex codes.

## Typography (essentials)

**Poppins** for everything (bundled in `assets/fonts/`, Open Font License):
Poppins **Medium** for headlines, **SemiBold** for sub-headings, **Light** for
body (Regular may substitute Light for web accessibility and very small sizes).
Always set type in **upper and lower case**. Italics only to emphasize.

**Segoe UI** is the alternative for Microsoft/Windows apps and email signatures
(it is the Windows system font - reference it, do not redistribute it).

Full type scale, pairing, and worked CSS: **read `references/typography.md`.**

## Logo (essentials)

The logo is **crafted custom art - never redraw, recolor, stretch, rotate, or
alter it.** Always place one of the bundled files from `assets/logo/`:

- **Horizontal** is the primary lockup (with or without the tagline).
- **Vertical** for narrow spaces and social avatars (never with the tagline).
- **Symbol** only for very small or icon contexts.

Clear space: at least **1/4 X** on every side, where **X = the width of the
Neutrinos symbol**. Minimum size: **25 px** high with tagline, **10 px** without.
Pick the color version that fits the background (full color on white/gray/blue,
all-white on dark, all-black when color is unavailable).

Bundled files and the eight "incorrect use" don'ts: **read `references/logo.md`.**

## Graphic system (essentials)

The recognizable Neutrinos visual devices - use them, don't reinvent them:

- **Symbol Supergraphic** - the symbol's angled lines extended (>= 1X) as a large
  background/watermark graphic.
- **Momentum Graphics** - particle "swirl" (circular, primary) and linear "wave";
  subtle, energy/speed. Represent particles of momentum.
- **Frame Brackets** - corner rules whose angle echoes the symbol; frame text and
  images; a good place for the one accent color.
- **The `.neu-tag` eyebrow** - the small Celeste-Blue label. This is the ONE
  permitted pill/rounded-label in the entire system. Every other pill badge,
  eyebrow chip, pill tab or pill CTA is BANNED (owner order, absolute) - never
  emit a `rounded-full` label anywhere except this one brand element.

Photography (Human + Conceptual), iconography (thin line + one solid accent), and
charts: **read `references/design-system.md`** and
**`references/photography-and-icons.md`.**

## Voice & messaging (essentials)

Personality: **bold & reliable; knowledgeable, competent & far-sighted; confident
& humble.** Write with quiet confidence and insurance domain credibility - a
challenger that hits the ground running, never hype for its own sake.

Tagline **Reinvent. Accelerated.** and the full messaging framework, elevator
speech, benefits, and boilerplate: **read `references/voice-and-messaging.md`.**

---

## Path contract

All Neutrinos skills are always installed as siblings. Within a skill, paths are
relative to that skill's own root (`assets/logo/...`). To reach brand-core assets
from another Neutrinos skill, use `../neutrinos-brand-core/assets/...`. Never use
a `skills/` prefix or a harness-specific variable such as `${CLAUDE_PLUGIN_ROOT}`.

## How to use this skill

1. **Read the reference file(s)** relevant to what you are making. Do not guess a
   hex value or a font weight - they are all written down here.
2. **Start from the tokens.** Inline or link `assets/tokens.css` (web/print/email)
   or read `assets/tokens.json` (any language) so values stay exact.
3. **Use real assets.** Reference the bundled logo, fonts, and icons in
   `assets/` rather than approximating them. See `references/assets-manifest.md`
   for the full file list and when to use each one.
4. **Then apply the matching media skill** for build mechanics:
   `neutrinos-web`, `neutrinos-print`, `neutrinos-documents`,
   `neutrinos-presentations`, or `neutrinos-social`.

## Reference index

| File | What it covers |
| --- | --- |
| `references/colors.md` | Every color value, combinations, screening, dark surfaces, contrast |
| `references/typography.md` | Poppins/Segoe scale, weights, pairing, CSS |
| `references/logo.md` | Configurations, clear space, min size, color versions, the 8 don'ts, file map |
| `references/design-system.md` | Principles, layout, supergraphic, momentum graphics, frame brackets, charts |
| `references/photography-and-icons.md` | Photography direction + sources, iconography rules, bundled icon library |
| `references/voice-and-messaging.md` | Positioning, personality, messaging framework, elevator speech, boilerplate |
| `references/assets-manifest.md` | Exact bundled files (logo/fonts/icons/tokens) and how to reference them |

## Quick brand check (use before shipping anything)

- [ ] White + Neutrinos Blue clearly dominate; at most one accent, used lightly.
- [ ] Headlines are black, Neutrinos Blue, or white - never an accent color.
- [ ] Type is Poppins (or Segoe UI on Windows), upper-and-lowercase.
- [ ] Logo is a bundled file, unaltered, with >= 1/4 X clear space and above min size.
- [ ] Layout has real open space and a modern, organized, slightly asymmetric feel.
- [ ] Tagline (if used) is "Reinvent. Accelerated.", uncolored, correctly placed.
- [ ] Voice is confident, knowledgeable, human - not hypey.