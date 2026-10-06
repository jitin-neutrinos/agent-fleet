---
name: jitinnair-portfolio-revamp
description: "Use when working on the www.jitinnair.com UX overhaul pipeline or the astra.jitinnair.com brand layer."
---

# jitinnair.com revamp + astra brand pipeline (kurama-core)

Repo: `/home/notjitin/Work/projects/jitin-nair-portfolio` (Next.js 14, Tailwind 3.4, framer-motion+GSAP; GitHub notjitin-1994 → Vercel; live = jitinnair.com). Work branch `revamp/ux-overhaul`; never push without Jitin's yes (push = deploy).

## Live route map (verified 2026-09-14; repo CLAUDE.md is STALE — /about /agents /case-studies 404)
`/`, `/ai`, `/ai/insights` (+9 slugs), `/ai/projects/<predator|smartslate|reality|revos|commune|localmind>` (no /ai/projects index), `/ld`, `/ld/capabilities`, `/ld/showcase`. Sitemap: /sitemap.xml. Scrape helper: `scratch/scrape.sh`, cached HTML in `scratch/scrape/`.

## Pipeline (SPEC: docs/revamp/SPEC.md; chain: scratch/chain.sh, state: scratch/chain-state.log)
1. Plan (style doc + audit + overhaul plan, docs 01-02): headless Hermes agent, `hermes chat --query-file scratch/prompt-plan.md --oneshot -m glm-5.3 --provider zai --reasoning high --max-turns 150 --in <repo>`. Runner: scratch/run-plan.sh, log scratch/glm-plan.log.
2. Build: `agy -p` Gemini 3.1 Pro High, accept-edits, runner scratch/run-build.sh.
3. Review + signoff (doc 04): another GLM 5.3 Hermes agent, runner scratch/run-review.sh.
4. Hermes final report; merge+push only after Jitin approves.
Claude was REMOVED from this pipeline at Jitin's request (2026-09-14) — plan/review run on GLM 5.3 Hermes agents. glm-5.3-flash also verified on zai.

## Gotchas learned
- Scroll-seam lessons (2026-10-06): the wheelAcc accumulator must be GESTURE-SCOPED (reset when the last event is >200ms old) — naive accumulation lets slow two-finger rubbing bank credit and fire surprise slides. Crossfade the OUTGOING card (opacity 0 like the old site) or the swap reads as a hard cut. Playwright mouse.wheel synthesizes momentum tails — unrepresentative; probe scrolls with dispatched WheelEvents (single ticks + timed bursts) instead. Gateway verdict "partial" on a gate call usually just means one claim lacked a probe — recheck, don't argue.
- Slide-1 buried-headline regression (2026-10-05): when porting ChooserHero to v2 HeroSlide, the text column lost 'relative z-10'; the absolute ParallaxPortrait + bg-black/75 overlay painted over static text. Diagnostic that tore it: elementFromPoint at h1 ink + COUNT LIT PIXELS in the headline band in screenshots (178 vs 11k was the tell). Vision tools can hit rate limits mid-debug — pixel-count fallback (Pillow, lit-pixel counts per band) substitutes. Every ported component needs its z-stack re-verified, not just markup parity.
- portfolio-v2 lessons (2026-10-05 fix-pass): Vortex.tsx rAF loop never stopped when hidden (idle spin); glow was TWO per-frame blur(self-draw) passes → single pass. Slides really pass particleCount:500 — don't assume copy-paste. Flash-of-last-slide: stacked absolute slides paint before lazy GSAP re-stacks → bar hidden (visibility) until GSAP claims the stack + opaque veil div; inline style ≠ DOM content, so SSR + client-injected style causes no hydration warning. Verify loop that worked: curl SSR for class presence, Playwright rAF sampler of computed opacity, reducedMotion:'reduce' context, /media/* sweep vs public/.
- Mobile audit doctrine (frontend-layout-measurement): marquee overflow reads as 7000px-wide elements but is CLIPPED by design — test with doc.scrollWidth==clientWidth before calling overflow broken. Tiny-target sweep (element rects <24px) works; density-aware sizing (44px mobile, tighter desktop).
- 2026-10-05 verified: test.jitinnair.com (:3105) serves ~/Work/projects/portfolio-v2/site (Next 14 + better-sqlite3 content DB snapshot of a Directus schema, Directus NOT running, NO git repo until fix-pass, now portfolio-v2 git repo) — NOT this repo. www.jitinnair.com serves THIS repo's pre-revamp main (revamp/ux-overhaul was never merged or pushed). Promotion path agreed with Jitin: finish v2 entirely, then promote it to www. Check which codebase the task means before working.
- `claude -p` non-interactive: raw curl BLOCKED unless `--allowedTools 'Bash(curl:*),WebFetch...'`; claude.ai session limit errors exit in ~2s with "session limit" in log — probe before long runs.
- Background terminal wrapper (setsid/nohup) is rejected by Hermes terminal tool — use background=true only.
- Hermes agent skill paths: skills load by NAME via skill_view, not ~/.claude/skills/ paths.
- The dashboard plan agent output uses a live-rendered pane log (glm-plan.log has ANSI/TUI frames) — grep for tool lines / final answers, don't read raw.

## Astra extension (docs 09-10 in ~/Work/astra)
R1 update-safety (no hermes-agent source edits; feature-detect SDK; extend eval_astra.py), R2 auto-port cron job on dashboard updates using glm-5.3-flash (detect via version+slot snapshot diff; report to Telegram; register cron only AFTER review signoff), R3 world-class chat UX (Claude-like streaming, 60fps batched token render, custom chat tab via gateway chat APIs vs TUI-embed decision required, attachments honest-if-unsupported, IIFE only, brand tokens from portfolio style doc, WCAG 2.2 AA). Brand gate: doc 10 plan waits on portfolio docs/revamp/01-style-documentation.md >8KB.
