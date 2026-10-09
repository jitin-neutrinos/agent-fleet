# Theme engine + animated backdrops (astra-webui repo)

Pipeline for palette work: `scripts/theme/compute-elemental.mjs` (OKLCH generator, hard asserts) → splice the emitted `ELEMENTAL` array into `scripts/theme/build-palette.mjs` → run it to regenerate `src/theme-engine/palettes.json`.

## Rules

- NEVER hand-edit `src/theme-engine/palettes.json` — `build-palette.mjs` rewrites it wholesale; a hand edit is erased on the next regen. Edit the generator, regen, commit both.
- Read the FIRST failure from `node scripts/theme/compute-elemental.mjs` before touching any palette value — the asserts name the exact gate (accent separation, hue world, slate ramp) and the failing hue.
- Keep every light-mode `void` at oklch L≈0.968 with chroma ≤0.014 — darker or higher-chroma voids cap the slate-ramp contrast (ink@55%-mix vs void) below the 4.5 gate even at the ink floor (oklch L 0.03 = #040404); the ramp loop then exhausts its guard and fails.
- Keep light-mode `brandtext` chroma near-neutral (≤0.012) — saturated inks drift on oklch re-derivation near black and the ramp loop never converges.
- Accent wheel: every accent must clear astra blue (hue 222) and every other accent by ≥40°; plan all four accents on the wheel TOGETHER before editing — one hue shift cascades into every neighbour's gate.
- Run `node scripts/theme/compute-elemental.mjs` (needs `scratch/` dir to exist for the emit step), then `node scripts/theme/build-palette.mjs`, then verify with `npx tsc -b` and `npm run build`.
- Deleting/renaming a palette is safe for clients: `currentPaletteId()` falls back to astra-ui and drops the stale localStorage key when a stored id no longer exists.

## Palette-switch reset pitfall (Android chrome bleed)

`theme-store.ts applyPalette`'s astra-ui branch clears EVERY inline `--*` custom property on `:root` except `FOREIGN_NAMESPACES`. Any new inline custom property another subsystem writes (e.g. `--native-inset-*` from shell-theme.ts) MUST be added to `FOREIGN_NAMESPACES` — otherwise switching to astra-ui deletes it, the cascade falls back to the stylesheet `:root` default, and the app's chrome collapses (observed as the Android status-bar/navbar bleed). `canvas-page-format.check.ts` pins this contract; extend its want-list when extending the namespace list. Also re-derive insets on `data-theme` flips — a theme change rewrites hundreds of inline props.

## Diagnosing bar/padding bugs from device telemetry

`~/.hermes/cache/scratch/astra-diag.jsonl` — append-only layout telemetry POSTed by native shell-theme.ts (`reportLayout`): env insets, nativeTop/nativeBottom, shell rect, theme, per boot and per theme-change. Healthy Android: nT=32px nB=16px. 0px/0px on theme flips with recovery after restart = the inline-prop wipe above. Parse with python json-per-line, never eyeball 1k+ rows.

## Repurposing Magic UI / registry components

- Fetch components as shadcn-registry JSON: `curl https://magicui.design/r/<name>.json`, take `files[0].content`. Same shape works for shadcn registries.
- Prefer zero-dep components; check `dependencies`/`registryDependencies` in the JSON before adopting. This repo already ships `motion`, `clsx`, `tailwind-merge` — `motion`-based components are free.
- Vite alias `@` → `./src` exists; keep upstream `@/lib/utils` imports (`cn` = clsx+tailwind-merge, already in `src/lib/utils.ts`).
- Tailwind-v4 project with no tailwindcss-animate: any `animate-*` class a component references (animate-meteor, animate-orbit, animate-ripple) needs its `@keyframes` + utility class hand-added to CSS (chat-backdrop.css holds the backdrop set).
- Components taking a canvas `color` prop (Particles) accept HEX ONLY — `hexToRgb` mangles CSS vars. Tint via the wrapper layer's CSS (color/opacity/mix-blend), not the prop.
- Backdrop CSS lives in `src/components/chat-backdrop.css` (imported by chat-landing.tsx), NOT index.css. Backdrop contract: `position:fixed; inset:0; z-index:0; pointer-events:none`, mounted inside ChatLanding's `<main>`; user's custom chat-bg always wins over generated scenes.
