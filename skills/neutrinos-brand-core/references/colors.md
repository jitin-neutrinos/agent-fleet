# Color

The Neutrinos palette is small on purpose. Two dominant colors carry almost
everything; a couple of neutrals support them; accents are a spark, never a fire.

## Core colors

| Name | HEX | RGB | CMYK | PMS | Role |
| --- | --- | --- | --- | --- | --- |
| White | `#FFFFFF` | 255, 255, 255 | 0, 0, 0, 0 | - | Dominant surface |
| Neutrinos Primary Blue | `#0066FF` | 0, 102, 255 | 100, 50, 0, 0 | 285 C | Primary / dominant |
| Mist Gray | `#F5F5F5` | 245, 245, 245 | 0, 0, 0, 5 | - | Light neutral surface |
| Midnight Blue | `#00053D` | 0, 5, 61 | 97, 55, 3, 58 | - | Deep / dark surface |
| Black | `#000000` | 0, 0, 0 | 0, 0, 0, 100 | - | Body copy text |

**Dominance rule.** White and Neutrinos Blue should be considered dominant for
all Neutrinos communications. Mist Gray and Midnight Blue may also be used, but
not as extensively as White and Neutrinos Blue. Black should primarily be used
for body copy text on white and gray backgrounds.

## Accent colors

| Name | HEX | RGB | CMYK | Alias |
| --- | --- | --- | --- | --- |
| Celeste Blue | `#00DEEF` | 0, 222, 239 | 100, 8, 0, 7 | "Energy Blue" |
| Mint Green | `#00EFAD` | 0, 239, 157 | 50, 50, 0, 0 | "Energy Green" |
| Salmon | `#FB327E` | 251, 50, 126 | 0, 81, 50, 2 | Coral |
| Iris | `#9A67FB` | 154, 103, 251 | 39, 59, 0, 2 | Lilac |

**Accent rules.**
- Accents add visual energy but should **never dominate** the design hierarchy.
- Use them **sparingly**. Only **one** accent color should be used together with
  the core colors in a given layout.
- **Two accent colors should never be combined** with each other - *except* in
  charts and graphs, where a fuller set is allowed for data differentiation.
- Celeste Blue is the accent most associated with the brand's UI furniture (the
  rounded "pill" section tags, small highlights).

## Headline color

Headlines appear **only** in Black, Neutrinos Primary Blue, or White. No accent
color is ever used for a headline.

## Approved color combinations

Core colors should dominate; accents are added minimally. All of these are
approved (from the Brand Book "Color Combinations"):

**Core only**
- White + Neutrinos Blue
- Mist Gray + Neutrinos Blue
- Neutrinos Blue + Midnight Blue
- White + Neutrinos Blue + Mist Gray
- White + Neutrinos Blue + Midnight Blue

**Core + one accent** (swap in Celeste *or* Mint *or* Salmon *or* Iris - one only):
- White + Neutrinos Blue + <accent>
- Mist Gray + Neutrinos Blue + <accent>
- Neutrinos Blue + Midnight Blue + <accent>
- White + Neutrinos Blue + Mist Gray + <accent>
- White + Neutrinos Blue + Midnight Blue + <accent>

## Screening (tints)

Any color may be **screened** (reduced opacity / tint) to create differentiation,
most usefully in charts, momentum graphics, and large background supergraphics.
Keep screened marks subtle so they never compete with foreground content.

## Dark surfaces

On **Midnight Blue** or **Neutrinos Blue** backgrounds, flip text to White and use
the all-white logo. In `tokens.css`, add the class `neu-dark` to the section to
swap the semantic roles automatically.

## Practical contrast guidance (digital / accessibility)

The Brand Book calls for accessible, legible design; apply WCAG sense-checks:

- **Black `#000000` on White** and **White on Midnight Blue `#00053D`** - strong
  contrast, safe for body text.
- **Neutrinos Blue `#0066FF` on White** - good for large text, headings, buttons,
  links. For small body text prefer black; test blue-on-white body at >= 16px.
- **White text on Neutrinos Blue `#0066FF`** - fine for headings and buttons;
  acceptable for short body. For long body on blue, prefer Midnight Blue panels.
- The bright accents (Celeste, Mint) are **low contrast on white** - use them for
  fills, shapes, and graphics, not for text on light backgrounds.
- Never rely on color alone to convey meaning (charts: add labels/patterns).

## Copy-paste values

Use `assets/tokens.css` (CSS variables `--neu-*`) or `assets/tokens.json`. Quick list:

```
Core:   #FFFFFF  #0066FF  #F5F5F5  #00053D  #000000
Accent: #00DEEF  #00EFAD  #FB327E  #9A67FB
```
