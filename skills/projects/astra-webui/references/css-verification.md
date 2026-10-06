# Verifying CSS-only changes (owner 10-03)

## Why not `npm run build`

`npm run build` runs `tsc -b` across the whole tree, so a single unrelated
in-flight TypeScript error hides a CSS regression — or makes you think you
broke something you did not. Compile CSS alone:

    node scripts/css-chat-surface.check.mjs

It builds through the real Vite/Tailwind pipeline into a throwaway
`dist-cssverify/` and never touches the served `dist/`. Extend it when adding
new chat-surface rules.

## Gotchas when asserting on emitted CSS

Four separate traps, all of which produce checks that PASS while the CSS is
wrong (found the hard way):

1. **lightningcss reorders declarations inside a rule.** `display` may come
   after `flex-direction`. Never substring-match a rule body — parse rules into
   selector sets + declaration sets, and take the last writer per property.
   Properties merge ACROSS matching rules: a later rule setting `z-index` does
   not erase an earlier rule's `scrollbar-width`.

2. **`color-mix()` is expanded into a literal hex PLUS an `@supports`-guarded
   `var()` form.** The hex is only the pre-color-mix fallback; the `@supports`
   branch is what every modern browser takes, and that is the theme-reactive
   one. Assert on the `@supports` branch.

3. **`@supports` preludes contain nested parens** (`color-mix(in lab, red, red)`),
   so `[^)]*` regexes silently fail to match. Brace-match the block instead.

4. **Chromium RESOLVES `margin-top:auto` to a used px value.** Asserting
   `getComputedStyle(el).marginTop === "auto"` fails against correct CSS. Assert
   GEOMETRY instead: measure the gap above and below the element.

Same class of trap in `scrollbar-color`: the computed value comes back as
`color(srgb 0.13 0.82 0.93 / 0.45)`, not the authored `color-mix(...)`. Compare
colour CHANNELS against the expected accent, don't string-match.

## Always prove the check can fail

Grep-matches and self-consistent assertions pass vacuously. Before claiming
done, mutate the shipped code and confirm the check goes red, then restore:

    cp src/lib/training-view.ts ~/x.keep
    sed -i 's/done++;/done += 99;/' src/lib/training-view.ts
    npx tsx src/lib/training-page.check.ts    # must FAIL
    cp ~/x.keep src/lib/training-view.ts

## Self-checks must import the shipped code

A check that restates the logic tests its own copy and passes even after the
page breaks. Put pure helpers in a plain module (`src/lib/training-view.ts`)
that both the component and the check import. Never have a component import a
`*.check.ts` — its top-level `main()` would execute inside the app bundle.

## Theme-reactive accents

Colour anything theme-driven off `--color-cyanx`, NOT a raw `--c-N` channel var
or a hex. That is the token `theme-store.applyPalette` already re-points per
palette AND per light/dark mode, so a widget follows a palette swap with no
`[data-theme="light"]` copy at all. Verified: all 24 palettes in
`src/theme-engine/palettes.json` define `--color-cyanx` in both variants.

## Deploy note

The server serves `dist/` statically, so a successful `npm run build` needs NO
`systemctl --user restart` — new asset hashes are picked up immediately. Verify
with `curl -s http://127.0.0.1:3011/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js'`
and compare against the filename in `dist/assets/`. A restart costs an approval
prompt on this box and is usually unnecessary.

## SPA routes need no server change

`server/server.mjs` has a catch-all SPA fallback (`file = join(DIST, "index.html")`),
so any new client-side page path works as soon as the client router knows it.