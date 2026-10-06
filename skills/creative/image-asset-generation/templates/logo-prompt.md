# Template: logo asset prompt (Nano Banana Pro via agy)
# Copy to scratch/prompt-logo-<name>.md, fill every <slot>, delete unused output entries.

## Context
Product: <name> — <one line what it is>. Visual family: <reference brand / style doc / approved file path>.

## Brand constants (use EXACTLY)
- Background: `<#hex>`; primary accent `<#hex>`; secondary accent `<#hex>`, used sparingly; wordmark/text `<#hex>`.
- Wordmark: "<word>" — all lowercase, exactly <N> letters, <font character, e.g. modern rounded sans>, generous letter-spacing, perfectly crisp.
- Vibe: minimal, premium, flat. <Solid colors only — NO gradients; single-color soft glow at most. / state the allowed treatment explicitly.>

## Motif
<one sentence — e.g. "fuse PLAY (triangle) + DOWNLOAD (downward arrow) into one glyph">

## Generate and save (create the folder if needed)
1. `<out-dir>/candidate-1.png` — <concept + composition, mark left + wordmark right>
2. `<out-dir>/candidate-2.png` — <alternate concept>
3. `<out-dir>/candidate-3.png` — <alternate concept>
4. `<out-dir>/icon-a.png` — mark alone, square 1:1, centered, ring ≈ <n>% of canvas, background `<#hex>`
5. `<out-dir>/icon-b.png` — <alternate mark alone, square 1:1>

## Composition rules
- Lockups: mark height ≈ 1.6× wordmark cap height; optically balanced; generous clear space; nothing else in frame.
- Favicon-safe: strong silhouette, legible at 32px; no hairlines that vanish at small size.
- Text rule: the only text in any image is "<word>", lowercase, exactly that. No taglines, no ".com", no extra symbols.

## Negative constraints (do NOT include)
Photorealism; 3D bevels; drop shadows on text; watermarks; extra letters/words; purple/magenta/pink hues; white or light backgrounds; busy detail; device mockups; frames or borders beyond the described mark; <brand-specific: e.g. NO GRADIENTS, no <secondary hue> in the logo>.

## Execution
Read <reference file path> first for the approved look. Use Nano Banana Pro. Save all files at the exact paths above; if one generation fails, retry once, continue, and report which failed. Reply with the absolute paths of everything saved.
