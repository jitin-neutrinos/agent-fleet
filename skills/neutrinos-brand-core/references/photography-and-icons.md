# Photography & Iconography

## Photography

The Neutrinos photography style has **two areas**:

**1. Human photography**
- People in **contemporary, simple contexts**.
- Choose subjects who look **natural and authentic**.
- **Avoid overly staged scenarios** (e.g. business people shaking hands, forced
  smiles at a laptop, generic "corporate stock").
- Real, candid, modern.

**2. Conceptual photography**
- **Abstract architectural** images that are **bold and graphic**, conveying
  **movement and light** (spiral staircases, sweeping curves, light studies).
- **Avoid** typical photos of high-rise buildings and cityscapes.

**Treatment.** Photos sit comfortably with big White/Blue/Midnight fields and
frame brackets. Cool, blue-leaning conceptual images pair especially well with the
palette. Keep compositions clean with open space.

**Recommended stock sources:** Stocksy.com, iStock.com, Pexels.com, Unsplash.com.

**Licensing.** Any photography used in real marketing must be **licensed before
use**. When you generate or place a placeholder, note that it needs licensing, and
prefer royalty-free/clearly-licensed sources for anything shipped.

## Iconography

Icon style = **thin lines combined with solid graphic elements.**

Rules:
- **Line elements** are **black or white** (match the background).
- **Solid shapes** inside the icon use **one Neutrinos accent color**, used
  **sparingly**.
- **Do not mix two different accent colors** within the same design/layout area.
- Keep icons simple, geometric, and consistent in stroke weight.

### Bundled icon library (`assets/icons/`)

The official icon set is included, organized by background and accent:

```
assets/icons/
  on-light/blue/    - black lines + Neutrinos/Celeste blue fills, for light backgrounds
  on-light/green/   - black lines + Mint green fills, for light backgrounds
  on-dark/blue/     - white lines + blue fills, for dark backgrounds
  on-dark/green/    - white lines + green fills, for dark backgrounds
```

Each folder holds the same ~63 icons (covering common concepts: protection/shield,
messaging, network/connection, people, speed, data, etc.). Filenames are the
original asset IDs (`icon-<id>.png`) - they are 4x PNGs with transparent
backgrounds. To pick an icon, read `assets/icons/index.json` - it maps each
concept to its asset ID - then reference the file in the folder matching your
background and single accent color. No image previewing is needed.

**Choosing icons for a layout:**
1. Pick the folder matching your background (light/dark) and your one accent.
2. Use icons from **that one folder** so the accent stays consistent.
3. If you need an icon not in the set, draw a new one in the same style (thin
   line + one solid accent shape) rather than importing an off-style icon.
