# Batch CSS transforms over index.css

Recipe for "change a visual law across every rule" asks (glow removal, radius
sweep, color migration). Hand-editing ~40 rules burns cycles; script it, assert
it, and keep the script so the next sweep is a one-liner.

## Why a script, not sed/hand edits
`index.css` is flat one-line rules. A sweep touches `text-shadow`,
`filter:drop-shadow`, and multi-part `box-shadow` values whose commas live
INSIDE `rgba()`. Every naive regex pass silently mangles or misses some rules.

## Parsing
- Split a rule body into declarations on `;` at paren-depth 0. Splitting on `,`
  looks plausible and is WRONG — commas are inside `rgba(34,211,238,.4)`, so you
  shred every multi-part shadow and end up "handling" 5 of 40 rules while
  believing you covered all of them. Count the generated overrides and sanity-
  check the number against the source count of matching declarations.
- Classify each `box-shadow` part: parse `rgba(r,g,b,...)`, colored when
  `max(r,g,b) - min(r,g,b) > 18`; also treat hex-with-alpha (`#22d3ee80`),
  `var(--color-*)`, token names, and bare `rgba(255,255,255,…)` highlight insets
  as glow. Everything neutral-black is elevation and stays.

## Glow-law application order (this is the part that bites)
1. **First** rewrite in place any EXISTING `[data-theme="light"]` rule that
   itself carries glows (e.g. a hand-tuned `.chat-composer:focus-within` with
   cyan halo layers). Keep its border/color changes; drop only the glow parts.
2. **Then** generate `[data-theme="light"] SEL { prop: … !important; }` for the
   remaining dark-only declarations.
3. Skip generation when a hand-tuned light rule already restyles that
   (selector, prop) — compare the TUPLE. Comparing the selector alone
   (or comparing a tuple against a set of strings) silently never matches, and
   step 1 becomes mandatory instead of an optimization.
4. Verify: grep the light rules and confirm zero colored shadows remain.

## Script heredocs: the abort-before-write trap
A python heredoc that does patch-work then `open(...,'w')` at the END only writes
if NO assert fires — an assert in the middle leaves the file untouched while the
earlier prints suggested progress. When a heredoc carries multiple edits, either
write after each edit, or treat ANY AssertionError as "nothing landed" and re-run
the whole script after fixing (check the file, don't assume partial application).
An assertion failure mid-script has twice meant the CSS edit silently never
happened while the session moved on as if it had.
## lightningcss output targets: the standard property can vanish
The vite build's lightningcss pass emits `-webkit-backdrop-filter` and may DROP
the unprefixed `backdrop-filter` for rules it believes the alias covers — modern
Chromium IGNORES the `-webkit-` alias, so computed style reads `none` and the
blur silently never renders (send/composer/bubbles all shipped once like this;
only a computed-style probe caught it). Rules:
- Author `backdrop-filter` WITHOUT the `-webkit-` twin in new rules when the
  build target is Chromium/WebView-first; if you must keep both, re-grep the BUILT
  css for the unprefixed property on YOUR selector, not project-wide counts.
- Debug pattern: `grep -o "\.selector{[^}]*}" dist/assets/index-*.css` — the
  minifier splits/merges rules, so count the rule occurrences and check EACH for
  the property (one selector had 6 emitted rules across fallback+@supports).
- `getComputedStyle(el).backdropFilter` returns `""` (not "none") in the
  -webkit-only case — assert with `includes("blur")` on std||webkit, and probe
  with a minimal `setContent` page when the app result looks impossible.

## WCAG contrast pass for generated palettes
For any generator producing dark+light variants per scheme, run a contrast audit
as a build step (`scripts/theme/a11y-pass.mjs`): text/muted ≥ 4.5:1 on void, UI
accents ≥ 3:1; auto-fix by stepping lightness (hue+sat preserved) toward the
needed direction (light bg → darken accent; dark bg → lighten), and RE-RUN to
convergence — pass 2 must report zero fixes. Two generator bugs only the audit
caught: light variants setting void AND brandtext to the same base slot (contrast
1.0 — ink must come from a DIFFERENT, darker slot than the paper), and
light-origin schemes whose "dark" variant kept the paper ground (force a genuinely
dark void: step `adjustL` until luminance ≤ ~0.09). Guard every derived default
with `contrast() >= 4.5` at generation time so the audit pass becomes a no-op.

## Glass + glow treatment defaults (owner mandate)
Content floating over a backdrop (bubbles, composer, header, welcome card, thinking/tool cards) gets a translucent ground + backdrop blur — expressed as `color-mix(in oklab, <ground> N%, transparent)` + standard-only `backdrop-filter`. Keep the scale consistent so "30% blur" style asks have a referent (composer ≈ 35px is 100%): bubbles 29px, header/cards ~10–35px by weight. Buttons that must "carry the theme color" (send, new-chat, stop) use an accent gradient `linear-gradient(var(--accent), color-mix(in oklab, var(--accent) 62%, var(--color-void)))` — precomputed dark-shade vars go near-invisible on pale accents. Bubble borders/glows: `color-mix(in oklab, var(--accent) 30% / 35%, transparent)`.

## Sibling lesson
Scripted sweeps need a pre-edit backup (`cp index.css ~/.cache/…bak`) and a
clean re-run from that backup on each attempt — a half-applied pass compounds
with the next one.

## Component restyles inside a shared dirty index.css
Large restyle asks (re-skin a whole control family) produce big multi-hunk
diffs in `src/index.css` that concurrent sessions keep dirtying. Sequence for
each batch: change source → `npx tsc -b --noEmit` → CSS check → build+restart
→ computed-style probe (sparse React props give computed values on first read,
not ones written to inline style) → commit ONLY your hunks via the signature-
filter + `git apply --cached` recipe (SKILL.md Pitfalls). Expect 2–3 commits
per ask when the tree is shared — leftover unstaged hunk references show up
when you grep the freshly committed file against HEAD, so re-diff and follow
up instead of assuming one filtered commit caught everything.

## Element restyle traps (live-verified)
- **CSS `fill:` and the SVG attribute `fill` fight; `color:` is what both
  follow when `fill=currentColor`.** Setting `fill="currentColor"` on the JSX
  (attrib) + `color:` on the class is the reliable way to make a lucide glyph
  solid and themed; styling `fill:` alone renders nothing on a stroke-only
  glyph whose attribute is `fill="none"`. When an element inherits an ink from
  a peer rule (e.g. a filled-chip svg rule), override BOTH `color` and `fill`
  in a LATER rule of equal specificity — source order decides, and the later
  block must be genuinely later in the file (.composer-bar-card .chat-chip-yolo
  svg lives after .chat-chip-icon svg).
- **`aria-checked`/state flips need the JS class AND the CSS keyed on the
  SAME attribute** — the button carries `role="switch" aria-checked={yolo}`;
  style the ON state via a class set in TSX (`chat-chip-on`) rather than
  `aria-checked` selectors, because the probe/explorer copies of the element
  don't carry aria state and their styling may then diverge from the real one.
- **Specificity math first, THEN write the rule: a media-query block does not
  add specificity.** A `@media (max-width){ .chat-welcome{max-width:…} }
  placed BEFORE the plain `.chat-welcome` rule loses to it at the same viewport
  (equal specificity, later source wins). Either place the mobile block AFTER
  the base rule or raise specificity. Symptom: the mobile fix works in a regex
  check on built CSS but the live element still uses the desktop value.
- **Rule-selection in a built CSS parser: identification by unique declaration
  beats positional `ruleFor`/last-match.** Multiple `.chat-composer-shell`
  rules (base + media variants) exist; `ruleFor` picks the LAST INCLUDING
  media-gated ones because the parser ignores @media context. Find the rule by
  a declaration only the target rule carries (`border:1px…`), and never expect
  the parser's Set members to have `.some()` — Set uses `[...set].some()`.
- **One card = one idea; land new block types as real standalone blocks
  beside the primary one, not merged into one giant multi-purpose card.**
  A KPI triple + a table + callouts + checklist compose one report card; a
  follow-on callout for an unrelated note is a SECOND card. First-emission
  shape must be `envelope` (top-level named fields wrap into blocks) or the
  whole card prints as code text with no error signal.
- **Anchoring that packs all leftover space to one side reads as wrong
  spacing even when the geometry is correct.** Center with auto/auto split
  (e.g. `margin-top:auto;margin-bottom:auto` on a flex item inside a flex
  column, NOT flex-end/justify-content which makes overflow-above
  unreachable in a scroll container). Distance proven by rect measurement
  (gap above/below or equal insets), updated in the CSS check file so the
  old anchor cannot silently return.
- **Minified output drops spaces inside `calc(100vw-32px)` and reorders
  shorthands; whitespace-normalise before regexing built CSS** — the check
  regex must match the minifier's ACTUAL output (`norm(css)` first), and a
  `:has()` parent selector test must grep the scoped-media-gated rule directly
  since valOf/ruleFor strips media context.
- **Record geometry before/after any spacing change in one probe script**:
  card/composer rects, gap-above/below, plate insets, plus the INTER-card gap
  (`barCard.top - inputCard.bottom`) — spacing asks are proved by numbers, not
  screenshots, and the same script doubles as the regression probe for the
  next spacing ask.
- **Parent wraps + scoped probes:** when wrapping two stacked cards in a new
  parent border/plate, set `overflow: visible` (absolute popups anchor to the
  chips inside), keep inner cards' own backgrounds (stacked translucency reads
  as one thick slab unless intentionally darkened), and assert visible rects:
  parent card inset (≈5px), parent radius (16px), focus ring should live on
  the PARENT (focus-within) not only on the child inputs.
- **Parent fills specify their media query ONCE, with sibling rules merged
  into the existing mobile blocks — never a second `@media (max-width: 360px)`
  later in the file restating the same declarations.** When styling bar
  children under a scoped parent wrapper (`.composer-bar-card .chat-chip …`),
  also neutralize the same classes inside any measurement/probe container
  that copies them (`visibility:hidden` measurement copies must NOT be
  restyled by their class chain). Rule: any restyle of a class that a probe
  span shares must carry a probe-neutralizing override in the same change.
- **A self-contained device that measures its host (`svg.parentElement`) is
  stock-still movable: re-parenting IS the feature change.** Its geometry
  (radius, border, size) follows the new parent automatically via the existing
  ResizeObserver. The consumers to re-scope are the CSS/JS that gated on its
  OLD host: focus-hide / opacity rules keyed `.oldHost:focus-within .trace`
  fire never once the trace becomes a child of the grandparent — move them
  to the new host. Confirm with a live probe: parent identity (`trace.closest
  === newHost`), rect == host rect, opacity at rest and after focusing an
  input.

## Adjacent: overlapping decorative layers
When a decorative element is drawn NEXT TO a border (animated trace, glow ring,
beam), a static border underneath reads as a duplicate outline. Fix it
structurally — make the idle `border-color: transparent` so the animation IS the
border, and fade the border back in on focus. Toggling the decorative layer
instead leaves a dead gap or a second line; both get reported back as the same
bug recurring. See `ui/border-beam.tsx` for the one-line-by-construction case.
