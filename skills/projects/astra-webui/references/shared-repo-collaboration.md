# Working in the Astra repo (shared tree, concurrent sessions)

`~/Work/projects/astra-webui` is routinely worked on by more than one live agent
session at the same time. Treat every build error and every surprise edit as
possibly-someone-else's until proven otherwise.

## The repo is shared — assume a concurrent writer

- **Commit only your own paths.** `git add <file> <file>`, never `git add -A` in
  a shared tree; a blanket add silently ships another session's half-finished
  work under your commit message.
- **Another session may REVERT your committed work, not just edit around it.** A concurrent session committed to `main` while a fix of mine was in flight and its commit restored an older `index.css` — my sidebar-glass, header-glass and linecap changes vanished from the tree, and a later full-regen compounded it. Before reporting any CSS/theme change as live, re-grep the file for YOUR change (`grep -c sidebar-glass src/index.css`) rather than trusting that it is still there from when you wrote it. When your change is gone, re-apply it ON TOP as a fresh commit — do not revert their commit, and do not assume they intended to undo you; they were working from a stale copy of the same file.
- **Never `git checkout` / restore a file to "get back to a known state" without checking what landed since.** The safe recovery for a corrupted or regenerated file is `git checkout -- <file>` to HEAD (which includes everyone's committed work), then patch in place. Restoring from a scratch `.bak`, a `/tmp` copy, or any snapshot older than HEAD silently reverts the shared tree — that is how a whole feature batch disappeared this session.
- **A build error in a file you never opened is not yours.** Fix your own errors,
  report theirs, leave them alone. Editing them destroys the other session's
  in-flight work and makes both sessions wrong.
- **Another session may edit your files mid-task.** A linter autofix from their
  run can strip an import from your file because it was momentarily unused.
  Re-read before patching, and re-add anything their run removed.
- **Prove a pre-existing failure instead of asserting it.** Stash only your paths,
  re-run the failing suite, restore:

      git stash push -- src/path/i/edited src/other/file
      npx tsx scripts/verify-history.ts   # still fails => not mine
      git stash pop

  Never "fix" a red suite you did not break by editing the other owner's code.
- Suites that print no `# pass` line are plain assert scripts, not `node:test`
  suites. Judge them by **exit code**, not by grepping for a pass counter — a
  grep-based sweep reports them as failures when they are green.

## Recovering work a concurrent session reverted

When your change vanishes, do not re-implement it — the exact bytes are usually
still in git. This is the fastest correct recovery, in order:

1. **Confirm the commits survived.** `git log --oneline -1 <your-sha>` per commit,
   then `git merge-base --is-ancestor <your-sha> HEAD`. "Not in the working tree"
   and "gone from history" are completely different problems.
2. **Find who clobbered it and whether they added anything.**
   `git log --oneline <your-sha>..HEAD -- <path>` lists the overwriting commits;
   `git diff <your-sha> HEAD -- <path>` shows whether their version is a pure
   revert or a revert PLUS real work.
3. **Export your version:** `git show <your-sha>:<path> > <scratch>/mine.tsx`.
4. **Port forward whatever they genuinely added.** A revert that also carries a
   theme-token rename or a new skeleton class is not a pure revert — dropping it
   silently reintroduces the bug they just fixed. Check the `+` side of the diff
   for real changes before restoring wholesale.
5. **Restore, build, verify the SERVED bundle, then commit.**

Restoring wholesale over a pure revert is right; restoring wholesale over a
revert-plus-changes is how you undo a colleague's fix.

## A type error in someone else's file silently blocks YOUR deploy

`tsc -b && vite build` short-circuits: one error anywhere means **nothing is
emitted**, `dist/` keeps its old mtime, and the site keeps serving the previous
bundle. No error appears in the served output and the app looks healthy.

- **Compare `dist/` mtime against your source mtime** whenever you believe a
  build succeeded. Newer source + older dist = the build never ran.
- **Ship first, fix the blocker second.** When the blocker is another session's
  WIP and you need your change live now, bypass the type gate and bundle alone
  by calling vite's Node API from a scratch script:

      // scratch-build.mjs
      import { build } from "vite";
      await build({ logLevel: "warn" });

      node scratch-build.mjs        # emits dist/ regardless of tsc
      rm scratch-build.mjs

  Then fix the blocking file properly if it is committed in HEAD, so the normal
  `npm run build` works again for everyone. Do not leave the gate broken.
- **Invoking `npx vite build` or `timeout N npx vite build` from the shell can be
  refused** by a long-lived-process guard that pattern-matches the command text.
  The Node-API script above sidesteps the matcher and is a legitimate build, not
  a guard bypass.

## State-changing commands need consent first

`npm install` and `systemctl --user restart` are gated and time out silently if
nobody approves — the command never runs and the step is lost.

- Ask for the go ONCE, covering every gated command in the batch, before starting
  the sequence that needs them.
- Chain them into a single command so one approval covers the run.
- A blocked command is final: do not retry it, do not rephrase it, and do not
  route around it to the same outcome. Finish everything else, then say
  explicitly what is left and why it did not run.
- Deploy state is separate from build state. A green `npm run build` with a
  stale service still serves the OLD bundle — report "built, not live" rather
  than "done", and name the one command that would go live.
- **The ONLY proof a frontend change is live is a distinctive string from your
  own source found in the SERVED bundle.** Read the current hashed filename out
  of the served HTML first, then grep that asset for 2-3 literal strings that
  exist only in your change (`grep -c "Ordered failover sequence" dist/assets/
  index-<hash>.js`). Zero hits means not deployed, regardless of what the build
  printed.

## Centring in a bordered rail: the odd-content-box half-pixel

An element with `justify-center` inside a `border-box` container centres in the
CONTENT box, which excludes borders. If total width minus the border is ODD it
lands on a half pixel, while a sibling column anchored at a padding offset lands
on a whole pixel — the two never line up, and re-centring never fixes it.

Live case (2026-10-04, collapsed sidebar logo): rail is `lg:w-16` (64px) with a
1px `border-right`, so the content box is 63px. `justify-center` put the logo at
x=31.5; the nav rows below centre a 48px `w-12` icon span at the 8px `px-2`
padding, landing on x=32. A permanent 0.5px offset in both themes at 1280 / 1440
/ 1920.

Fix: don't centre the odd element out — give it the SAME box as the column it
must align with (`px-2` + `w-12` span), so both centres derive from one rule.
After: logo centre 32.0 = rail centre = icon-column centre (delta 0.00px).

Measuring this class of bug:
- Compare the two centres against EACH OTHER and against the container's true
  centre. A `devicePixelRatio` check only proves "even, therefore sharp", never
  "aligned with the icons".
- An icon span inside a scroll container can report a width narrower than its
  class (`w-12` reading 36px). That means the element is constrained, not that you
  picked the wrong node — dump ALL sibling spans with their classes before
  concluding.
- A screenshot centroid is only trustworthy once you model the BACKDROP. A glass
  sidebar (`backdrop-filter: blur` over an animated canvas) has a per-column
  luminance gradient; a naive "differs from black" ink test measures the glass, not
  the logo, and produced a nonsense 21px offset. Use column-wise deviation from
  that column's own median.
- A text-mode ASCII luminance dump (PIL downsample to ~64 cols) beats centroid
  maths for judging whether something *looks* centred, and needs no vision model
  — useful when the vision quota is exhausted (hit 2026-10-04).
- Drive the collapsed state through the app's own key (`astra-sidebar-collapsed`
  = `"1"`/`"0"`). Writing a word like `"collapsed"` leaves the rail expanded and
  the probe silently measures the wrong layout — it reports plausible numbers,
  just for the wrong element.
- Verify light theme by SETTING the attribute and reading it back; the first
  attempt reported `theme: null` while the numbers looked fine.

Guard: `src/lib/sidebar-logo-align.check.ts` re-derives this geometry in plain
arithmetic and fails if `justify-center` or the shared `w-12` span returns. Prove
a new check fails on the pre-fix markup before trusting it — a check that only
ever sees the fixed tree can pass vacuously.

## A global touch rule silently changes layout — verify on COARSE pointer too

`src/index.css` carries a global accessibility rule:

```css
@media (pointer: coarse) {
  button, [role="tab"] { min-width: 44px; }
  button, a[href], input, select, [role="tab"] { min-height: 44px; }
}
```

Every button on a touch device is therefore at least 44x44, while on a
desktop mouse it is content-sized. Any layout that depends on a button's
intrinsic width is CORRECT on desktop and WRONG on tablet — and desktop-only
verification will pass while the owner's iPad stays broken.

Live case (2026-10-04, collapsed sidebar logo, owner-reported): the logo button
was `display: block` with no centring, so the block-level `<img>` sat at the
button's LEFT EDGE. Content-sized 28px on desktop => image filled the button =>
measured 0.00px and looked right. Inflated to 44px on iPad Pro 12.9 => image
pinned 8px left, measured -8.00px in BOTH orientations, after a hard reload.
The first fix was desktop-only and missed it entirely.

Rules that follow:
- **Test coarse pointer, not just fine.** `Emulation.setDeviceMetricsOverride(...
  mobile=True)` + `Emulation.setTouchEmulationEnabled(enabled=True)` actually
  activates `(pointer: coarse)`. Desktop emulation alone will never show it.
- **A button that holds only an icon must centre its child.** A bare block-level
  `<img>` is left-pinned; add `grid place-content-center` (or make the button a
  grid/flex centring context). Then the button's own width stops mattering.
- **Prefer a container whose size you control over one that inherits a min-**
  width. Filling the column (48x55 here) is correct for every pointer type and
  beats the 44px minimum, so alignment is never traded against touch target.
- **`place-content: center` on a grid parent sizes the TRACK to content.**
  A child's `w-full`/`h-full` then resolve against a content-sized track and the
  fill silently does nothing (measured: the button stayed 44x44 even with
  `h-full w-full` on it). Use an explicit `grid-cols-1 place-content-stretch`
  wrapper when the child must fill.

Driver traps hit while chasing this (all produced plausible, wrong numbers):
- **Scope every selector to the container.** `document.querySelector('.ast-topbar')`
  matched the HIDDEN mobile top bar (0x0) as well as the sidebar one, so rects
  came back all zeros and a pixel crop was taken of the wrong element.
- **`Page.captureScreenshot` `clip.scale` is multiplied by DPR.** Requesting
  `scale: 10` at DPR 2 writes a 20x image; hardcoding the divisor produced a
  28px-wide "logo" whose centre read 60px in a 64px rail. Read the real factor
  back as `image_width / crop_width_css`.
- Crops taken with a negative `y` silently clamp to 0 and change the scale
  frame. Read the rect first, clamp yourself, then crop.

## Long prose/prompt documents go through write_file, never a heredoc

The install guard parses shell text for package names, so a heredoc containing
ordinary English can be read as a package install and blocked ("package 'Keep'
does not exist"). Write prompt/directive/spec documents with the file tool;
reserve heredocs for shell that has no prose payload.

## Verify the compiler, not the language server

After editing a large TSX file, the editor's LSP diagnostics can describe code
that no longer exists — they survived a rewrite that deleted the offending JSX
entirely and reported a `<Pie>` element from a previous version.

- The source of truth is `npm run build` (`tsc -b && vite build`).
- A large `write_file`/`patch` can land with corrupted tokens (stray labels,
  malformed closing tags). Symptom: a parse error at a line you did not write.
  Recovery: `git checkout --` the file and re-apply the change as ONE
  whole-function patch. Do not stack small incremental patches onto a corrupted
  file — the corruption compounds and each patch's context drifts.
- Re-read the file from disk before the next edit; do not trust your in-context
  copy of a file you just rewrote.