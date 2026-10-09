---
name: design-shape-rules
kind: reference
scope: astra-webui UI builds (shape, motion, brand compliance)
---

# Design / shape / motion rules — reference

Always-on rules from `neutrinos-brand-core` + `astra-webui` standing orders,
condensed for quick lookup during a build/review phase.

## Brand shape law (hard, owner order)

**NO pills, ever (absolute).** Rounded-full badge/eyebrow/label chips are banned in every
design on every surface, forever. No decorative pill labels, no pill tabs, no pill CTAs.

NO `9999px` / `rounded-full` / `border-radius: 50%` / pill shapes except:
- Sub-8px decorative status dots / pulse indicators (`.suba-pulse`, `.bgd-pulse`). These are indicators, not interactive shapes.
- A genuinely circular icon wrapper nested inside a button (e.g. the arrow chip).
- Everything interactive takes `border-radius: 10px` (30px elements → 10px; 34px send → 10px; 16px tabs → 6–8px proportionally). Never a circle.

Status/severity chips that carry real state use a small radius (`rounded-md`), never
`rounded-full`. The only Neutrinos-branded exception is the `.neu-tag` eyebrow.

## Touch-target counter-rule fix (pitfall)

Global `@media(pointer:coarse){ button,[role=tab]{ min-height/min-width:44px } }`
defeats single-class counters. A compact pill's counter must name BOTH selectors:
`button.x, [role=tab].x { min-height:0; min-width:0; padding:3px 8px; }`. Bare `.x`
only ties `button` and loses to the later `button` + `[role=tab]` pair.

## Running border line (SVG dash, constant length)

Conic-gradient traces STRETCH AT CORNERS — degrees near a rounded corner cover
more physical border. Use an SVG `<rect rx=12 pathLength={100}>` stroke with
`stroke-dasharray: 26 74` (dash = constant fraction of real perimeter — same on
straights and through corners) + `animation: composer-trace-run 6s linear infinite`
(`to { stroke-dashoffset: -100 }`). Size in real pixels (ResizeObserver) so `rx`
matches CSS `border-radius`. Sharp cap: `stroke-linecap: square`. Reduced motion:
`display: none` the trace (`.composer-trace { display:none; }`) — a frozen arc reads
as broken; do NOT freeze with `animation: none`.

## Partial command-color overlay (mirror technique)

Textarea cannot color a substring. Mirror overlay: `.cmd-active { color:transparent;
caret-color:accent; }` + absolute `.cmd-mirror` with identical padding/font over
it. Mirror must render WHOLE input: `<span class="cmd-slash">/</span><span>
{cmdWord.slice(1)}{args}</span>`. Bare `/bg` with only args rendered = empty visible
text — the original bug. `visibility:hidden` hides the `/`, NOT the command text.
Send uses raw input untouched (`send()` sees `/cmd args`); mirror is display only.
Ceiling: no scroll-sync past ~9 lines (`max-height: 200px`), unrealistic for commands.

## /bg vs /steer separation (different mental models)

- `/bg` = run-after queued job (`prompt.submit { queued:true, surface:webui }`).
  Job tracker surface: queue badges (`#1`, `#2`), elapsed timer (`fmtElapsed`),
  reply-jump chevron (`.bgd-go`), input field for follow-ups. Persisted in
  localStorage per session (`localStorage.getItem(bg_items_${sid})`).
- `/steer` = live turn course-correction (busy-mode bridge). NO queued flag.
  Inline receipt in timeline: quotes correction (`.steer-note`), live/running/
  applied state; never in the dock. In-flight lock (`steerBusyLock`) prevents
  concurrent steers on one turn.

## Light-mode glow stripping (automated)

Every `text-shadow`, `filter: drop-shadow(...)`, and `box-shadow` containing
`rgba(34,211,238,...)` / `cyanx` / violet / fuchsia / emerald must be removed
in light mode. A script parses declarations (semicolon-separated, paren-aware for
nested `rgba(...)`) and generates `[data-theme="light"] .selector { prop: none/stripped !important; }`.
Keep neutral black elevation (`rgba(15,23,42,...)`, `rgba(0,0,0,...)`) intact; only
drop the colored-glow parts.

Always verify against the SERVED bundle (`index-BpBraG1V.css` / `.js`), not
`src/`: minifier reorders shorthand (`animation:6s linear infinite astra-trace-run`).

Usage: `node ~/Work/slop-score/slop-score.mjs`, `~/Work/ai-slop-detector/.venv/bin/slop-detector`.
