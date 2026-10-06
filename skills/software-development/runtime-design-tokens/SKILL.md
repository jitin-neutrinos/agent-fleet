---
name: runtime-design-tokens
description: "Use when making a visual token user-changeable at runtime."
version: "1.0.0"
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [design-tokens, theme-engine, css, tailwind, postcss, typography, shape, branding]
    related_skills: [astra-webui, astra-webui-regression-fixes, tailwind, dispatching-parallel-agents]
---

# Runtime design-token engines

## When to Use

Reach for this when a task involves any of:

- Making a visual property **user-changeable at runtime**: corner shape, type stack,
  logo/app name, density, motion, spacing scale.
- A theme engine, a design-token system, or a "let the user pick X" settings surface.
- **A user-changeable token that appears not to take effect** — the symptom of a
  build-inlined value, an undefined `var()`, or a reset path that wipes foreign
  namespaces. Start at the feasibility gate below.
- Retiring hardcoded literals (radii, colours, shadows) onto a token scale.

Not for static stylesheet authoring with no runtime layer, or design work that changes
content but no tokens.

The subject is any app that COMPILES CSS (Tailwind, PostCSS, Vite/webpack). These
tokens are the contract between the stylesheet and the engine; the mistakes below are
all silent.

## Feasibility gate — run this FIRST, before planning anything

A runtime token system only works if the compiled utilities still hold a `var()`
reference. Source and build can look identical and disagree. Grep the built stylesheet
in your bundle directory (`dist/assets/index-*.css` and equivalents):

```bash
grep -oE '\.(font-sans|rounded-lg|rounded-2xl)\{[^}]*\}' dist/assets/index-*.css
```

- Utilities show `var(--token)` → runtime override works. Proceed.
- Utilities show a literal (`.rounded-lg{border-radius:.5rem}`) → the build inlined
  the value; a runtime override of that token does nothing and the feature will
  "work" in dev and silently fail in prod.
- `@theme inline` in source resolves token values at COMPILE time, producing exactly
  that inlining. It is the usual culprit and is invisible in the source file.
- Non-`@theme` `:root` custom properties are never inlined, so they are always safe
  runtime targets — which is why a mixed codebase can have both behaviours at once.

If the answer is "inlined", the fix is build configuration, not a new engine. Establish
this before designing anything; it is one grep and it decides the whole approach.

## The silent-failure family: undefined `var()`

A custom property that is referenced but never defined is invalid-at-computed-value.
The declaration is dropped, the property takes its **INITIAL** value, and **nothing is
logged**. `border-radius` initial is `0px`, so a phantomed radius renders square —
plausible enough to survive review and ship. `color` phantoms render transparent;
`--spacing-*` phantoms collapse layout.

Find them by set difference, never by reading the definitions block:

```bash
grep -oE 'var\(--[a-z0-9-]+' src/index.css | sed 's/var(//' | sort -u > /tmp/used
grep -oE '^\s*--[a-z0-9-]+:' src/index.css | tr -d ' :' | sort -u > /tmp/defined
comm -23 /tmp/used /tmp/defined      # every phantom token
```

`calc(var(--phantom) - 4px)` fails identically. Verify the fallback in a real browser
before asserting it — the spec reading and the observed value should agree:

```js
// undefined var() → "0px"   defined → "12px"   calc(undefined) → "0px"
```

`scripts/find-undefined-css-vars.sh` automates this for a given stylesheet.

## Sizing a codemod before writing it

Retiring hardcoded values is mechanical only if you histogram them first. Take the
value histogram of the target property; **its shape IS the migration map**:

```bash
grep -o 'border-radius:[^;}]*' src/index.css | sed 's/border-radius://' | tr -d ' ' | sort | uniq -c | sort -rn
```

~15 distinct px values collapsing into a handful of buckets means a small lookup table,
not 200 judgement calls. Split the count by `var(--` vs literal too: the token-driven
declarations are already done and must not be touched. Handle the odd shapes explicitly
rather than letting them fall through a naive regex — `50%` is a circle, not a radius;
4-value shorthands like `12px 12px 0 0` are asymmetric composites, not scale steps.

## Runtime engine hazards

- **A reset path that wipes inline custom properties destroys any other engine.**
  Before persisting a token with `root.style.setProperty('--mine', …)`, find every code
  path that clears inline properties and check it excludes foreign namespaces. A common
  shape is a "reset to default" branch that loops `[...root.style]` and removes anything
  starting with `--`, which looks harmless while only one engine wrote props and silently
  eats the second. Pin it with a check.
- **Prefer a data attribute on the root for MODE-like values, and a token for magnitude.**
  A mode attribute (`data-shape="sharp"`) reads as intent in devtools and needs no
  per-element opt-out. See `references/shape-and-scale-architectures.md` for the proven
  multiplier architecture and the published token scales worth stealing from.
- **A pill is a separate token, not a large value.** Define the "full/pill" token as `0`
  (or the scale's minimum) by default and flip it only in pill mode, then have components
  compose `max(var(--shape-n), var(--shape-full))`. This way anything that must never
  pill — code blocks, images, caret-aligned inputs — simply references the scale step
  directly and is immune, instead of needing a manual opt-out per component. A fixed
  "pill" token holding a mid value is a latent bug: on a short control it can never read
  as a pill.
- **Touch targets survive a shape change only if you compensate.** A 28px icon button in
  a circle mode is a 28px target. Grow the hit area with an `::after` pseudo-element
  rather than inflating the visual size, and keep any coarse-pointer minimum rule as the
  backstop.
- **A user's own long string must degrade.** For an editable wordmark/app name, measure
  the text once, auto-scale down to a FLOOR (clamp ~0.62), and only then let ellipsis
  take over — without the floor you produce unreadable 4px type. Also put `min-width: 0`
  on every flex/grid ancestor, and use a container query rather than a media query to drop
  to a logomark-only variant, since it must respond to the container not the viewport.

## Migrating a hardcoded stylesheet to tokens

Prefer a **build-time codemod** over runtime overrides. Runtime overrides need
higher-specificity rules, lose to any late declaration, and hide the remaining literals
instead of eliminating them. A codemod is reviewable, idempotent, and provably complete
because the literal count reaches zero.

Give it the same shape as any idempotent codemod in the repo: detect your own output and
no-op on re-run, provide a reset that restores from **git** (never from a stale `.bak`
snapshot, which silently reverts other people's work), and keep a histogram assertion so
"zero literals left" is a measurable claim rather than an intention.

## Runtime-editable assets (fonts, logos, icons)

A sync/persistence endpoint with a request-body size cap makes inlining impossible:
upload the binary to a server-side asset route and persist only its URL, exactly as
backdrops already do. Serving fonts by proxying the provider's CSS and rewriting each
`url()` to a locally cached file keeps the app self-hosted — no third-party request at
runtime, no API key. Render uploaded SVG via `<img src>`, which cannot execute script;
if you must sanitize server-side, an allowlist tokenizer beats regex (regexes cannot parse
nesting, so mXSS survives), and beware two bugs that break GOOD logos rather than bad
ones — lowercasing attribute names kills `viewBox`/`preserveAspectRatio`, and a `\s`-based
control-character strip eats the spaces inside path data.

Runtime `<link rel>` rewrite is sufficient for favicon/apple-touch-icon/manifest; no
service worker is needed. Cache-bust the href with a version query or browsers keep the
old asset, and keep manifest `src` root-relative (relative paths resolve against the
manifest's own directory).

**Measure a browser's request credentials before assuming a gated asset route works.** A
manifest fetched from a cookie-gated route can arrive with no cookies at all, and the
dependent icons then fail the same way; the fix is a `crossorigin` attribute on the
`<link>`, and the durable simplification is to serve manifest/icon routes **ungated** when
they carry nothing secret (a name and a logo in a single-tenant app). Cross-origin
`@font-face` is the mirror case: it needs `Access-Control-Allow-Origin` or the load fails
silently into the fallback, while a same-origin cookie-gated font works with no header at
all. Verify with a server-side request log and a real `document.fonts.load()`, not by
reading the handler.

**Enumerate a provider's catalogue with a keyless, CORS-open endpoint, and verify it.**
Well-known metadata endpoints are sometimes not fetchable from a browser at all, so a
client-side list is impossible and the list must be proxied or bundled — check the
`access-control-allow-origin` header before designing around an endpoint. When one is
reachable, fetch the full list once and search client-side; a `?search=` parameter may not
be supported even when the bare list is.

**Read a font's own name from the file, not the filename.** A zero-dependency parser
(`zlib.brotliDecompressSync`/`inflateSync` plus a table walk) yields the real family,
subfamily, variable flag and weight axis range; the file's family string routinely differs
from the marketing name, so the picker must display what the font says it is. Two traps
worth inheriting from a working implementation: a WOFF table is stored **raw** when
compressed length equals original length (skip inflating), and a reconstructed woff2 table
stream takes **no** 4-byte padding, because padding yields garbage name ids.

- **A token that a prompt-level rule tells authors to emit must survive EVERY layer, not just the parser.** A rulebook is only enforceable if the key it names reaches the renderer. A new envelope key is dropped twice by default: once when the spec object is built (it enumerates the keys it keeps) and again when the render-time sanitiser rebuilds a clean spec (same failure, different file). The symptom is a card that parses cleanly, validates cleanly, and renders in the default format anyway — indistinguishable from the rule being ignored. Add the key to both builders, and pin BOTH with a check: valid values survive, and an unknown value is DROPPED rather than coerced (a silently-accepted `"portrait"` is how a rule ends up naming a value the renderer never honoured). Where a key is optional, omit it entirely when absent rather than setting it `undefined`, so specs written before it existed stay identical.
- **A phantom-var scanner needs an exclusion list, and each exclusion needs its own pinned precondition.** The set-difference scan flags every token that is legitimately supplied from OUTSIDE the stylesheet — a page component writing its width as an inline style, a grid setting its column count from JS, the framework's own internal style hook. Blindly "fixing" one sends you editing a file with no defect in it, and excluding blindly re-opens the hole the scan exists to close. Exclude by prefix, then assert each excluded read carries its own CSS fallback; the exclusion is only safe while the fallback holds.

## Pitfalls

- **Retiring hardcoded literals is two-part, and shipping half of it is worse than
  shipping none.** A runtime override of the scale tokens only moves the utilities that
  already resolve to them; the hand-written literals keep their old values and the app
  renders half-transformed, which reads as a bug rather than a setting. When a stylesheet
  mixes both, the codemod and the scale must land in the same change, or the token set ships
  unused. Confirm after by re-running the literal histogram: the count must reach zero,
  not merely decrease.
- **Planning a token engine before confirming the build keeps `var()` references** —
  one grep decides viability, and the source file will not tell you.
- **Assuming a token exists because it is used.** A referenced-but-undefined property
  is invisible in every tool and renders at its initial value.
- **Counting "how many hardcoded values" from memory or a rough grep** and reporting
  the estimate to the owner. A research child corrected a parent estimate of ~600 to a
  measured 252, which is what prompted the hunt that found the real bug. Measure, then report.
- **Rewriting already-token-driven declarations** in a codemod — they are the destination,
  not the work.
- **Treating every `border-radius: 9999px` as scale drift.** Those are deliberate circles.
- **Letting one engine's persistence path be the only writer of a shared namespace**
  without a check that pins the other engines' namespaces survive a round trip.
- **Trusting a subagent's report verbatim.** Children do catch parent errors, and they
  also over-generalise: a partial probe becomes a stated rule whose confounder goes
  unreported. Re-test every load-bearing claim with the cheapest probe that matches its
  type — an HTTP status matrix, a grep of the built bundle, a run of the library — and when
  a child's claim contradicts your own earlier reading, re-run the child's probe before
  your own. See `references/subagent-report-retrieval.md` for reading a full report out of
  `state.db` (the live transcript stores it truncated) and for the correction-and-credit
  pattern.
