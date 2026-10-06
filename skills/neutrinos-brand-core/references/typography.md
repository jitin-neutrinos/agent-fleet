# Typography

Type is where the "clean, modern, professional, open" personality mostly lives.
Keep it Poppins, keep it upper-and-lowercase, keep it generously spaced.

## Primary typeface - Poppins

Poppins (from Google Fonts, Open Font License) is used for all print and digital
applications whenever possible. It is bundled in `assets/fonts/`:

| File | Weight | Primary use |
| --- | --- | --- |
| `Poppins-Medium.ttf` | 500 | **Headlines** |
| `Poppins-SemiBold.ttf` | 600 | **Sub-headings** |
| `Poppins-Light.ttf` | 300 | **Body text** |
| `Poppins-Regular.ttf` | 400 | Body substitute for web accessibility / very small sizes |
| `Poppins-LightItalic.ttf` | 300 *i* | Emphasis in body |
| `Poppins-SemiBoldItalic.ttf` | 600 *i* | Emphasis in sub-headings |

Rules:
- **Always upper and lower case.** Do not set all-caps runs of text.
- **Italics only to emphasize** a word or for grammatical call-outs - never as a
  dominant design element.
- On the web, prefer **Regular (400)** over **Light (300)** for body at small
  sizes so text stays legible and accessible.
- The logotype itself is drawn from TT Norms Pro; you do not need that font - use
  the bundled logo art. Poppins is the brand's working typeface for everything else.

## Alternative typeface - Segoe UI

Use **Segoe UI** for Microsoft/Windows applications (PowerPoint, Word, Outlook)
and **email signatures**, where Poppins may not render. It is the closest Windows
system font to Poppins.

- Segoe UI **Semibold** for headlines, **Segoe UI Regular** for body.
- Segoe UI is a Windows system font - **reference it, do not redistribute it.**
  (That is why only Poppins is bundled here.)

Font stack to use in CSS / documents:
`"Poppins", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif`

## Loading Poppins on the web

Either use the bundled files via `@font-face` (already declared in `tokens.css`,
pointing at `./fonts/*.ttf` - adjust the path to your build) **or** Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;1,300;1,600&display=swap" rel="stylesheet">
```

For self-contained artifacts where external CSS is blocked, base64-embed the
bundled TTFs in a `@font-face` `src: url(data:font/ttf;base64,...)`.

## Type scale

Modern and open. Default web scale (1rem = 16px); scale down proportionally for
dense UI, up for hero and print covers.

| Token | Size | Weight | Use |
| --- | --- | --- | --- |
| Display | 4.5rem / 72px | Medium 500 | Hero headline, cover title |
| H1 | 3rem / 48px | Medium 500 | Page title |
| H2 | 2.25rem / 36px | Medium 500 | Section headline |
| H3 | 1.5rem / 24px | Medium 500 | Sub-section |
| H4 / Sub-head | 1.25rem / 20px | SemiBold 600 | Sub-heading, eyebrow |
| Body | 1rem / 16px | Light 300 (web: 400) | Paragraphs |
| Small | 0.875rem / 14px | Regular 400 | Captions, metadata |
| Caption | 0.75rem / 12px | Regular 400 | Fine print, labels |

Line height: **1.1-1.2** for headlines, **1.6** for body (open and readable).
Headline letter-spacing slightly tight (`-0.01em`); body normal.

## Headline color reminder

Headlines: **Black, Neutrinos Blue, or White only.** Body copy: Black on light,
White on dark. Never color a headline with an accent.

## Worked example (CSS)

```css
h1 { font: 500 3rem/1.15 "Poppins","Segoe UI",sans-serif; letter-spacing: -0.01em; color: #000; }
h1.blue { color: #0066FF; }
.eyebrow { font: 600 0.875rem/1.2 "Poppins",sans-serif; color: #0066FF; text-transform: none; }
p { font: 300 1rem/1.6 "Poppins",sans-serif; color: #000; }
@media (max-width: 640px){ p { font-weight: 400; } }  /* legibility at small sizes */
```
