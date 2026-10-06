---
name: react-headless-render-probe
description: "Prove React component behaviour with no browser — tsx + react-dom/server probes, and the traps (classic JSX runtime, node_modules resolution, probes pointed at the wrong git tree)."
version: "1.0.0"
author: Hermes Agent (session 2026-10-04, astra-webui canvas reactive parser)
license: MIT
metadata:
  hermes:
    tags: [react, tsx, ssr, renderToStaticMarkup, testing, no-browser, git-worktree, probes]
    related_skills: [dogfood, hermes-web-ui-qa, astra-webui-performance]
---

# React headless render probes (no browser)

For when a check suite covers the pure logic but the React half — state seeding,
value resolution, render guards — has no DOM gate. `tsx` + `react-dom/server`
proves it in about 15 lines.

## The recipe

```bash
# run from the project root: tsx must resolve node_modules for the probe
npx tsx probe.mts
```

```ts
import * as React from "<abs>/node_modules/react/index.js";   // see trap 2
(globalThis as unknown as { React: unknown }).React = React;  // see trap 1

const { renderToStaticMarkup } = await import("<abs>/node_modules/react-dom/server.js");
const { Widget } = await import("<abs>/src/components/widget.tsx");  // see trap 1
const html = (renderToStaticMarkup as (e: unknown) => string)(
  React.createElement(Widget as never, { prop: "x" }));
```

Assert on substrings of `html` (class names are stable anchors), not on
rendered text you cannot see animate.

## Traps (each one cost a failed run before it was understood)

1. **tsx compiles JSX with the CLASSIC runtime.** `React` must exist as a
   global before the component module loads, or the first provider throws
   `ReferenceError: React is not defined`. Static imports are hoisted and run
   first, so set the global at the top and load every `.tsx` module through
   **dynamic `await import()`**.
2. **A probe file outside the repo cannot resolve bare `react`.** You get
   `ERR_MODULE_NOT_FOUND` — the probe's own directory has no `node_modules`
   ancestor. Import `react/index.js` and `react-dom/server.js` by absolute path
   into the project's `node_modules`.
3. **A probe with an absolute import into the WRONG git tree measures the wrong
   code.** A shared/PM-authored probe that hardcodes `/path/to/repo/src/x.ts`
   keeps reporting the primary checkout's behaviour inside an isolated git
   worktree, no matter what the worktree contains. Verify with `stat -c %i` on
   both files (same inode = same file) and `git worktree list`. Then copy the
   probe into the allowed temp dir with ONLY the import repointed, run BOTH, and
   report the verbatim gate as unpassable-by-construction rather than editing
   someone else's probe or the primary checkout.

## Reading the output honestly

- Animated/count-up components render a **pre-animation placeholder frame** in
  static markup (`200` → `"000"`). A bare number in the markup proves nothing;
  a non-numeric formatted string (`"$250,000"`) appearing verbatim does — use
  it as your assertion.
- Prefer a **contrast pair**: render the same component once with the input that
  should resolve and once without. "Showed a value" is weak; "showed `$25,000`
  with the seeded default vs `—` without it" is proof the fix is load-bearing.
- A working probe is not a substitute for a browser check when the change is
  interaction (drag, focus, animation). Say which one you ran.

## Evidence

Proven on astra-webui's canvas card (M2 reactive-parser session
20261004_124053_693de4): a `renderToStaticMarkup` probe confirmed a control's
authored default reached the reader expression's scope (`money(seats*price)`
rendered `$250,000`, and `$25,000` when the default was removed), and that a
bound chart series survived parsing without throwing in the label derivation.
The worktree trap is documented in `~/Work/projects/astra-webui/ARCHITECTURE.md`
under "Headless render probes".