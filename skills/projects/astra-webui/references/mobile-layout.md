# Mobile layout: drawer vs paint-order lifts (2026-10-02, commit 1efa2b7)

## The bug
`aside#astra-sidebar { position: relative; z-index: 2; }` (added at 5c75fc6 to beat a fixed z-0 chat backdrop on desktop) out-specifies Tailwind's `.fixed` utility at EVERY viewport. Below lg the drawer computed `position: relative`: translated -100% but still IN FLOW, it reserved its 288px slot in the flex row — the chat pane collapsed to a 124px sliver. Owner saw: "chat crammed to the right, background eating 75% of the phone viewport" (the reserved slot reads as empty background).

## Fix
Scope the lift inside `@media (min-width: 1024px)` in `src/components/chat-backdrop.css`. The lift is only needed where the aside is static (lg+); on <lg it is fixed z-50 and cannot be buried by the z-0 backdrop.

## Lessons
- Symptom signature: an element holds layout space while its translate says off-screen. Check COMPUTED `position` first (`getComputedStyle`), not the JSX classes — the classes were correct; a CSS rule was winning. Any `position` in an ID/later rule beats utility positioning classes regardless of source order.
- A paint-order/z-index fix written unconditionally for one layout state silently breaks the other state. Scope positioning overrides to the breakpoint that needs them.
- Verify BOTH modes after any positioning fix: at 412px main.w === innerWidth AND drawer opens (x=0 on tap); on desktop the sidebar is visible/unburied WITH a backdrop set.
- Probes: `scratch/layout-probe.mjs` (computed-style chain), `scratch/live-mobile-check.mjs` (live site at Pixel 7 with minted cookie), `scratch/header-dump.mjs` (per-element header rects). Reusable.
- Sibling sessions edit this repo concurrently: check file mtimes before AND after your edits, `grep` the wiring of any half-finished feature before "fixing" it, and expect your patches to be superseded mid-session (the end-session header chip built here was replaced by the sibling's sidebar-row-menu design within minutes — its design won, owner order 10-02).
- 44px global touch-target rule (`@media (pointer:coarse)`) sizes EVERY header button to 44px width — three right-aligned 44px buttons on a 412px phone overflow into the nav button's slot. Count the touch targets before adding header controls on mobile.

## Source-vs-bundle verification (audit and 'is X fixed?' work)

**Verify fixes against the deployed bundle, not the source tree.** A fix that exists in `src/` but not
in the built `dist/assets/index-*.js` (or the APK bundle under
`android/app/src/main/assets/public/assets/`) is not shipped — audit reports must grep BOTH trees, then
run `npm run build` (and rebuild the release APK) to close the gap. Minified bundles rename identifiers:
grep stable string literals (class names like `composer-field`, error strings, URL fragments), never
exported symbol names.

**Date the artifacts first in any astra audit** (commit time, dist mtime, APK bundle mtime): the phone's
WebView loads the server dist over the tunnel (capacitor `server.url`), so server-side fixes reach the
phone without an APK rebuild — but an APK bundled before a fix remains an audit red flag for that
surface. HTML is `no-cache`, hashed assets `immutable` (server.mjs static handler); a hard reload
decides "cache vs unshipped".

**Full bug-verification audit shape** ('are my bugs fixed?'): grep each fix signature in source + both
bundles → date artifacts → live-server auth probe (login → cookie, cache-busted `?_r=<epoch-minute>`
curl through the tunnel AND locally; confirm the server data behind the symptom before diagnosing
client code) → `npm run check` with gate-failure classification (duplicate `RG-\d+` pinned ids = repo
hygiene, re-id the second set; interpreter/SQLite-version failure = environment constraint) → report
verified-vs-inferred per row. Depth: `references/check-suite-and-ci.md` §7.
