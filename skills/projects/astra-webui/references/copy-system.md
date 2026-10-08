# Copy-button system (astra-webui UI)

Every copy affordance goes through ONE system. Never hand-roll a copied-state button.

## The contract
- `src/lib/copy-text.ts` is the ONLY code that touches `navigator.clipboard`.
- `src/lib/animated-copy.tsx` `AnimatedCopyButton` is the only React copy button. Pick a variant: `action` (chat action rows), `float` (code-block hover; legacy `sm` prop maps here), `chip` (labelled header chip for canvas card / code / terminal heads). It owns copied state, the 2s revert, aria/title labels.
- `src/lib/rich-pre.ts` `wireCodeCopyButtons(root, copyText)` wires per-`<pre>` buttons into markdown HTML; its DOM-built buttons reuse the same classes as the React ones (no private style injection).
- All skins live in ONE index.css block near `.chat-code-copy`: shared swap animation (`.chat-copy-swap` / `.chat-copy-ic` / `.is-check`) plus the three skins `.chat-code-copy`, `.chat-actions-copy`, `.chat-copy-chip`.

## Rules
- New copy surface → reuse `AnimatedCopyButton` with a variant, or add a parent-scoped CSS override of an existing skin (e.g. `.ai-term-bar .chat-code-copy { position:static; ... }`). Never a second state machine, timer, or icon ternary; never a direct clipboard call.
- Deleted one-off skins (`.ai-term-copy`, `.ast-canvas-copy`, `.ast-cv-copy-swap`, `cc-*`) stay deleted.
- `float` renders `position:absolute` — inside a static bar, override position under the parent class in CSS rather than stacking `!` utilities in JSX (a CSS override survives refactor; JSX `!` spam fights the cascade). Tailwind `!` utilities are the fallback when a one-off skin (e.g. a vault row) shouldn't touch index.css.
- The chip skin carries `margin-left:auto; flex:none` so it right-aligns in `space-between` heads and long titles can't shrink it — keep both when touching it.
- **Canvas card-header chips are ICON-ONLY (owner steer).** A `label` widens the chip to its text, crowding the `.ast-canvas-head` flex row until it bleeds past the card's right edge on narrow phones. Drop `label` and keep `title` — `AnimatedCopyButton` keeps `aria-label`/tooltip, so discoverability survives; the Copy→Check swap already tells the story. Icon-only in the head; labelled chips elsewhere (editable docs captions) are fine where the row has room.
- **Every copy button is a BARE icon — no plate, no outline (owner steer, whole family).** Rest state = `background:transparent; border:none`; hover tint alone carries affordance. This applies to all three skins and their parent-scoped variants: `.chat-actions > *` (no glass chip/blur), `.chat-copy-chip` (28px icon box, no pill chrome), `.chat-code-copy` float (no glass plate/outline; also scrub dead `border-color` lines from parent-scoped overrides — a stale `border-color` re-arms an outline if the base border ever returns). Geometry stays per-skin (44px action rows, 28px head chips, 22px terminal-bar). Do not reintroduce a fill/border "for discoverability" — the icon + hover + swap animation is the affordance, per owner reversal precedent.

## Check-suite conventions
- `src/lib/copy-system.check.mjs` sweeps src/: fails on clipboard bypasses, duplicated skin rules, resurrected dead skins, private swap classes. Pinned as a REGRESSIONS row in `scripts/regression-gate.check.mjs`.
- Every new `*.check.*` file MUST get a row in the gate's REGRESSIONS manifest — a discovery sweep fails the whole gate on any unpinned check.
- The gate re-runs pinned checks from DISK: an unpinned check file another agent left uncommitted fails the suite for everyone. Don't pin or 'fix' foreign checks; leave them to their author.

## Known-red baseline (verify around, don't fix)
- `scripts/sqlite-runtime.check.mjs` fails while the host Node bundles SQLite < 3.51.3 (WAL-reset bug) — an interpreter problem, fixed by a Node upgrade, not by a repo change. Its crash also paints the regression gate red with "1 regression-gate failure" — classify that as the same environment red before reading the gate as a product regression, and prove any diff innocent with a stash-isolation re-run on the clean tree (see `check-suite-and-ci.md`).
- Run `node scripts/run-checks.mjs` BEFORE a change to learn the baseline; after it, require only 'same failures as before, none new'. Don't chase pre-existing reds.

## Build + deploy
- `npm run build` (tsc -b && vite build) is the gate; the >500 kB chunk warning is pre-existing advisory noise.
- dist flips on the next request without a server restart; `systemctl --user restart astra-webui.service` is harmless belt-and-braces.
- Verify live: `curl -s https://astra.jitinnair.com/api/health` → 200, then grep the served `assets/index-*.css` for a marker string from the change — a build that didn't ship reads as success otherwise.

## Shared working tree
- Several agents commit to this repo's working tree. Before editing a file, `git status` / `git diff` it: uncommitted hunks you didn't write are someone's live work — never commit, revert, or build on them blindly.
- Commit only your paths. When a foreign hunk sits inside a file you must commit, split the diff into hunks, keep yours, write the filtered patch to `.git/`, and `git apply --cached` it before commit.
