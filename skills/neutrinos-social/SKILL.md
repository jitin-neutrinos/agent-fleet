---
name: neutrinos-social
description: >-
  Create on-brand Neutrinos social media and digital ad graphics - LinkedIn and
  Facebook posts, banners, covers, avatars, ad creative, meeting backgrounds,
  email signatures. Use for any Neutrinos social post, banner, cover, ad, or
  "make a post/banner/ad in our brand". Correctly-sized, bold graphics using
  the real logo, Poppins, and brand devices. Read neutrinos-brand-core first.
license: Proprietary
compatibility: Requires an agent that supports the Agent Skills format (SKILL.md).
metadata:
  version: "1.1.0"
  brand-book: "Neutrinos Brand Identity Guide"
  source: "https://github.com/jitin-neutrinos/neutrinos-designer"
---

# Neutrinos Social & Digital Ads

Bold, scroll-stopping, unmistakably Neutrinos: dominant blue/midnight, a big
Poppins statement, one graphic device, the logo, and one accent.

**Always read `neutrinos-brand-core` first.** Build each graphic as an
HTML/CSS canvas at the exact pixel size, then screenshot/export to PNG/JPG (e.g.
headless Chromium, or render at 2x for crispness).

## Common sizes (px)

| Asset | Size | Notes |
| --- | --- | --- |
| LinkedIn post (square) | 1200 x 1200 | Also 1080 x 1080. |
| LinkedIn post (portrait) | 1080 x 1350 | Best feed real estate. |
| LinkedIn company cover | 1128 x 191 | Keep text clear of the profile logo overlap (lower-left). |
| LinkedIn personal cover | 1584 x 396 | |
| Facebook post | 1200 x 1200 | |
| Facebook cover | 1640 x 856 | Safe area centered. |
| Profile / avatar | 400 x 400 | Use the **vertical** or **symbol** logo, centered, on white or blue. |
| Instagram post / story | 1080 x 1080 / 1080 x 1920 | |
| Digital ad (LinkedIn single image) | 1200 x 627 | |
| Twitter/X header | 1500 x 500 | |
| Virtual meeting background | 1920 x 1080 | Subtle - see below. |

Always confirm current platform specs if it matters; sizes shift over time.

## Layout patterns

- **Statement post:** Midnight Blue or Neutrinos Blue field, one bold
  Poppins-Medium line ("Reinvent. Accelerated.", "Outcomes. Not Code.", "Built for
  Speed."), the white logo, a screened momentum swirl or the supergraphic bleeding
  off a corner. Minimal words.
- **Announcement / value post:** white or mist-gray; blue headline; short body in a
  frame bracket; one library icon (single accent); logo bottom.
- **Carousel:** consistent template across slides - same margins, logo position,
  and one accent; vary the headline per slide.
- **Digital ad:** brand header (small logo + "Reinvent. Accelerated."), a bold
  visual (supergraphic, momentum swirl, or conceptual photo), the value line, and
  a short supporting sentence - mirroring the Brand Book's ad examples.

## Covers & avatars

- **Company/personal banners:** dark or blue field with the supergraphic bleeding
  in from the right, logo + tagline on the left; keep important content out of the
  area the platform overlaps with the profile picture (lower-left on LinkedIn).
- **Avatar:** the **vertical** logo or the **symbol**, centered, on white or
  Neutrinos Blue; keep clear space; it must read at small sizes.

## Meeting backgrounds

Subtle and professional: a Neutrinos Blue / Midnight field or clean white with a
**screened** supergraphic or momentum graphic to one side, a small logo in a
corner. It should sit behind a person on camera without competing - keep the center
and one lower third calm for the speaker.

## Email signature

Layout to match the Brand Book:
- **Segoe UI** (system font on Windows) - Regular for the address/contact block,
  **Bold** for the person's name.
- **Black** for all contact text.
- Horizontal logo placed below the sign-off at a small, consistent size.
- Structure: Name (bold) / Title / phone(s) / website, then the logo.
- Deliver as an HTML signature snippet (inline styles, table layout for email
  clients) plus a plain fallback.

## Rules (social)

- Dominant white/blue/midnight; **one** accent; Poppins (or Segoe UI where a
  system font is safer, e.g. signatures).
- Headlines black/blue/white only; big and few-worded.
- Correct logo version for the background, full clear space, above min size; use
  the **symbol** or **vertical** logo for small/avatar contexts.
- One graphic device per asset; keep real open space even in a square.
- Two accents never combined in one graphic.
- Photography must be licensed for anything published.

## Export

Build the HTML canvas at the target size (set `width`/`height` on the root,
`overflow:hidden`), then render to image:

```bash
# example with playwright/chromium; render at 2x for crisp output
python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1200,"height":1200},device_scale_factor=2)
    pg.goto("file:///abs/path/post.html"); pg.screenshot(path="post.png"); b.close()
PY
```

Then run the brand-core Quick Brand Check before handing it over.