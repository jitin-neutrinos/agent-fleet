# Session 20261003_184420 — Unverified / known-broken at handoff

Facts proven in this session, kept here so the next reader does not re-learn them (or worse,
re-ship them as fixed). Everything NOT in this file that the transcript showed passing IS fixed —
these are the three things that did NOT land.

## 1. Composer-bar click blocker — UNRESOLVED (reported fail, not absorbed)

While the composer options popup is OPEN, every click inside the popup AND on the composer bar
buttons is swallowed: the reasoning chip cannot close it, the options trigger cannot reopen or
retarget it, and the provider/model drill-down rows do not navigate. Measured with
`elementFromPoint` over the reasoning chip: top element is `DIV.cmenu-plate`, not the button.

Ruled out BY MEASUREMENT (each one, not by inspection): one component instance; one popup;
dismiss ref inert for internal clicks; no form; no click interceptor; full ancestor chain accepts
pointer events; trusted CDP `Input.dispatchMouseEvent` click fails identically to synthetic; the
failure reproduces on the PREVIOUS committed build (predates the session's work).

Three fixes were landed and ROLLED BACK after each measurement (see config-page-patterns.md §"roll
back speculative geometry"): per-panel keyed motion wrappers; pointer-events bound to the active
panel; absolute panel overlays (fixed the overlap, shrank the plate to 2px, then sizing the plate
broke the options trigger again). Debug live with the popup open, not another blind CSS attempt.

## 2. Chip 44px tap targets — attempted, not achieved

The `::after inset:-5px` hit extension on `.chat-chip-icon` answers clicks 1–3px outside the
button but NOT at 5px. z-index, removing the wrapper's `max-height`, and `overflow: visible` all
failed. Send button uses an identical mechanism (`inset:-8px`) and works — so the technique is
sound and something specific to the chips' ancestor chain is interfering. Visual sizing (34×34@10px)
was completed; only the tap-target floor is missing. Practical effect: 34px tap target on touch
screens instead of the WCAG 2.2 AA 44px. User told; keep digging only on request.

## 3. 'Mutant gate' — query not answered, loop-burned

The owner asked "bg / what is a mutant gate? why does it take so long?" after seeing something in
the bg-dock / gate UI. Effort went into ledger greps (`data/gate-ledger.jsonl`, ntfy polls) looking
for a literal "mutant" string, which never appears in the ledger, the guardrails, or the bg code —
the question was NOT answered before context ran out. Note for next time:tirith guardrails score
fuzzy risk for compound/nested commands (e.g. anti-slop loop batches, `rm -rf` audit clones), which
is what Jitin sees as a slow gate; "mutant" is the snippet of his own text running inside the
gate's reason text, not a real gate kind. Direct answer should have been: it's the Tirith/Laya
approval scoring shell commands before running them, and yes it can wait on explicit timeout —
click once early ("Allow once") to unblock the agent.

## Bonus grab-bags of fact, not broken items
- Ledger cleanup probe (`mutl98o3-probe2.png` etc.) was removed; good.
- `find ~/Work -maxdepth 3 -name capacitor.config.ts` — multiple worktrees carry their own
  `capacitor.config.ts` (astra-theme worktrees, scratch/lightbase) — a config-change sweep must
  enumerate ALL of them, not just `~/Work/projects/astra-webui`.
