# Chat bubbles — solid fills (owner mandate 2026-10-07)

Chat bubbles (`.chat-turn` = assistant, `.chat-bubble-user` = user) are SOLID OPAQUE FILLS, not glass. `backdrop-filter` is REMOVED from both selectors. Do not reintroduce it.

## Token contract (in `src/index.css` `:root`, with a `[data-theme="light"]` override block)

```css
--bubble-ai-bg: var(--color-accent);                       /* FULL accent, both modes */
--bubble-ai-border: var(--color-accent);
--bubble-ai-code-bg: color-mix(in srgb, var(--color-accent) 80%, #000 20%);
--bubble-ai-inline-bg: color-mix(in srgb, var(--color-accent) 80%, #000 20%);
--bubble-ai-ink: #04121a;                                  /* dark ink for text on accent */
--bubble-user-bg: #1f2229;      /* light mode: #2a2d33 */
--bubble-user-border: #1f2229;  /* light mode: #2a2d33 */
--bubble-user-text: var(--color-brandtext); /* light mode: #f3f6fb */
```

Selectors `.chat-turn` and `.chat-bubble-user` carry no `backdrop-filter` and no `transparent`-mixed background.

## The accent-on-accent trap (the reason this file exists)

When the AI bubble's background IS `--color-accent`, anything inside painted in `--color-accent` disappears into the fill. After flipping the bubble to solid, audit EVERY markdown child that uses the accent and re-ink it to `--bubble-ai-ink`:

- `.chat-turn .chat-md h2` (was accent)
- `.chat-turn .chat-md a` (was accent, also add `text-decoration: underline` because the colour no longer signals a link)
- `.chat-turn .chat-md strong` (was `--color-brandtext`)
- `.chat-turn .chat-md h4` (was `--color-muted` — use a 70% mix of ink)
- `.chat-turn .chat-md blockquote`, `.chat-md hr`, `.chat-turn-ts` (use 65% / 30% ink mixes)
- `.chat-bubble-ai { color: ... }` streaming pill (was accent on transparent — now MUST be ink)

Same trap runs in reverse on the user bubble if its fill ever goes accent-coloured.

## The later-rule-wins trap

`index.css` declares some of these overrides TWICE — once near the `:root` token block and again further down the file (e.g. `.chat-turn .chat-md strong` around line 1524 AND again around line 2306). CSS source order means the LATER rule wins. A patch that only edits the first occurrence is silently shadowed and the visible bug stays. When fixing bubble ink, `grep -n` for the selector and edit EVERY match, or scope your fix tighter (`.chat-turn .chat-md …`) so it outranks the loose rule regardless of order.

## The action row inside the bubble (copy / edit / regenerate)

The row is absolutely positioned bottom-right INSIDE the bubble (`.chat-actions`; the bubble is the positioning context, so it must keep `position: relative`). Geometry lives in two coupled numbers — set them together:

- `.chat-turn, .chat-bubble-user { padding-bottom }` — reserve below the last text line
- `.chat-actions { right / bottom }` — the row's inset

The row clears the text only while reserve >= inset + row height. On an overlap report raise reserve AND inset together: a bigger reserve at the old smaller inset leaves the icons crowded into the rounded corner.

The buttons are BARE ICONS on the bubble surface (owner steer) — no tinted chip fill, no `backdrop-filter` on `.chat-actions > *`. Glass on glass doubles the frosting and reads as noise; the hover tint on `.chat-actions button:hover` carries feedback.

## Verification chain

After any bubble-colour change:
1. `npx tsc -b --noEmit`
2. `npm run build`
3. `systemctl --user restart astra-webui.service && systemctl --user is-active astra-webui.service`
4. Resolve the CURRENT hashed CSS name from the served page — `curl -s http://127.0.0.1:3011/ | grep -oE 'assets/index-[^"]+\.css' | head -1` (never reuse a hash from notes; vite rewrites it every build)
5. `curl -s http://127.0.0.1:3011/assets/index-<HASH>.css | grep -oE -- '--bubble-(ai|user)-bg:[^;}]+'` — expect the new values in BOTH `:root` and `[data-theme=light]` scopes
6. `grep -oE '\.chat-turn\{[^}]+\}'` — expect NO `backdrop-filter` on the bubble selectors
7. `set -a; . ~/.config/astra-webui/env; set +a; bash scripts/selfcheck.sh http://127.0.0.1:3011` — expect ALL PASS

Lightningcss emits each `color-mix` twice (a flat fallback plus an `@supports` block) — that duplication is normal, not a bug.
