# 2026-10-02 regression spree — deploy-pipeline, video-fixture and stacking-guard lessons

Full write-up lives in the project: `~/Work/projects/astra-webui/docs/regression-spree-2026-10-02.md`
(shipped table with commits + proofs, UNRESOLVED list, fixture traps).

Skill `astra-webui-regression-fixes` carries the generalized procedure. This file
records only the session-specific facts worth keeping next to the project:

- Commits this session: `0ce485d` (actions row inside bubble — landed by the
  concurrent session), `0a428f6` (comet linecap butt), `f51cece` (sidebar z-guard +
  bgSrc host-path rewrite + chat-backdrop.src.check.ts), `f65a621` (End session
  moved header -> row menu + linecap actually shipped + header/sidebar glass
  aligned), `1f5c68c` (shared top-bar height token).
- Build-blocker RESOLVED: `f65a621` cleared the TS6133 (`doEndSession` unused).
  The recurring "butt fix is back" reports were this — src said `butt`, served CSS
  said `round`, because the failing build never wrote dist. Verified fixed by
  grepping the SERVED hashed CSS. The `.wt-build` workaround worktree was removed.
- End session moved to the `ast-row-menu` in `chats-panel.tsx`; the destination
  item pre-existed as a stub, so `doEndSession` moved into ChatsPanel and the
  fetch + view reset moved up into Shell as `onEndSession`, with
  `astra:end-session` (sid-scoped) telling ChatLanding to suppress the greeting.
  Header button and its arm/confirm state deleted from chat-landing.tsx.
- Top bars unified on `--astra-topbar-h` (56px); `h-16` + `py-4` removed from the
  logo row, logo h-9 -> h-7.
- STILL PENDING: the unified slash popup was build-green and committed but was
  never visually verified in a browser — check it before trusting it. Also the
  `bgSrc` rewrite and sidebar z-guard were verified live, but the composer comet
  tail artifact has only been proven via A/B pixel capture on the corner origin,
  never along the full perimeter sweep.
- Fixture files `probe*.mp4` and the `/home/notjitin/chat-bgs/` dir were cleaned up
  after testing; `data/theme-state.json` was restored to the owner's real backdrop
  via `PUT /api/theme/state` (tests overwrite it through the server sync).
