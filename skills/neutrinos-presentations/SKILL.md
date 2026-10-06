---
name: neutrinos-presentations
description: >-
  Build on-brand Neutrinos presentations and slide decks - pitch decks, sales
  decks, webinars, QBR decks - as PowerPoint (.pptx) or HTML slides. Use for
  any Neutrinos presentation, deck, slides, pitch, or talk in the brand.
  Applies the official template style: blue/midnight title slides, Poppins,
  supergraphic, frame brackets. Read neutrinos-brand-core first.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md).
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Presentations

Decks that match the official Neutrinos PowerPoint template: bold blue/midnight
title and section slides, calm white content slides, Poppins type, the symbol
supergraphic, and momentum graphics used sparingly.

**Always read `neutrinos-brand-core` first.** Choose PPTX (editable, the usual
ask) or HTML slides (for the web / an artifact).

## Format choice

- **PowerPoint (.pptx)** - default for business decks people will edit/present.
  Read the `pptx` skill for build mechanics; set fonts to **Poppins** with
  **Segoe UI** fallback (Segoe UI is safe on any Windows machine), and apply the
  slide system below. If a **Slides** artifact type is offered by the host and the
  user hasn't asked for a file, prefer that per the host's guidance.
- **HTML slides** - for a web talk or an artifact (e.g. reveal.js-style or simple
  full-viewport sections). Use `tokens.css`.

## Slide system (from the Neutrinos template)

- **Title slide** - white background, horizontal logo top-left, the **symbol
  supergraphic** (blue line) bleeding from the top-right, a Neutrinos-Blue
  Poppins-Medium **Presentation Title**, black sub-title, date. A frame-bracket
  underlines the title.
- **Section slide** - full **Neutrinos Blue** field, white logo, white
  Poppins-Medium **Section Title**, a screened **momentum swirl** top-right.
- **Content slide** - white; blue Poppins-Medium title with a thin frame-bracket
  underline; body as concise bullets (Poppins Light/Regular); one accent for
  emphasis. Lots of open space - few words per slide.
- **Closing slide** - "Thank You" in Neutrinos Blue with the supergraphic bleeding
  in from the top-right; contact / neutrinos.co.
- **Footer** - a slim Neutrinos-Blue bar with the small white symbol and
  "(c) Neutrinos | Confidential and Proprietary | page" (optional on content slides).

## Type & color on slides

- **Poppins** everywhere (Segoe UI fallback for Windows/PowerPoint).
- Titles: Poppins **Medium**; body: Poppins **Light/Regular**; labels: SemiBold.
- Titles **Neutrinos Blue on white**, **white on blue/midnight** - never accent.
- One accent per slide for a highlight or a single data series.
- Dominant white and blue; midnight blue for section/impact slides.

## Graphics on slides

- **Supergraphic:** the extended symbol line, bleeding off a corner, blue on white
  or lighter-blue on midnight. Keep it behind/beside content, never over text.
- **Momentum swirl:** screened, top-right of section and impact slides.
- **Frame brackets:** under titles and around callout text/quotes.
- **Charts:** core colors dominant, accents secondary, screened tints to
  differentiate series; Poppins labels; donut/bar/line/stacked-bar/horizontal-bar
  as in `neutrinos-brand-core/references/design-system.md`.
- **Icons:** the bundled library - one accent, matching the slide background.
- **Photography:** conceptual (abstract architectural, movement/light) or authentic
  human shots; framed with brackets; must be licensed for external decks.

## Content rules

- **One idea per slide.** If a slide has three ideas, make three slides.
- Headlines do the work; bodies are short. Prefer a bold statement + one visual.
- Keep the deck's rhythm: title -> section -> a few content slides -> section ->
  ... -> thank you.
- Use the messaging language from `../neutrinos-brand-core/references/voice-and-messaging.md`
  ("Reinvent. Accelerated.", "Outcomes. Not Code.", "Built for Speed.").

## PPTX build notes

- Set theme fonts (Headings + Body) to **Poppins**; embed the bundled TTFs if the
  audience may lack Poppins, or accept the Segoe UI fallback.
- Set theme colors: Text/Background from White/Black/Midnight; Accent 1 =
  Neutrinos Blue `#0066FF`; Accent 2 = Midnight `#00053D`; then Celeste/Mint/
  Salmon/Iris as accents 3-6 (use one at a time on a slide).
- Place the logo from `neutrinos-brand-core/assets/logo/` (SVG or PNG) with clear
  space; use `neutrinos-symbol-white.png` from `../neutrinos-brand-core/assets/logo/` in the footer bar.
- Reuse the symbol supergraphic and momentum swirl as picture elements bleeding
  off slide edges.

## Verify

Render/preview a few slides and run the brand-core Quick Brand Check: white/blue
dominant, one accent per slide, Poppins, correct logo + clear space, real open
space, titles only black/blue/white.