# Astra CLINIC — canvas/card debugging procedure (astra-webui repo)

The astra-webui repo renders generative-UI cards through a fail-soft pipeline (parser → sanitizer → renderers) where EVERY layer re-implements the block contract BY HAND (per-type field lists, per-type switch cases). The same card shape can therefore be dropped at any layer by a hand-maintained case list missing "the new field" — and each layer has its own gates that never test the others.

## Recurring card bug: the procedure

1. **Verify the prior fix is LIVE** — curl the public URL and compare the served hashed bundle against `dist/`, or grep the bundle for a string unique to the current fix. A mismatch means the build/deploy chain is stale; fix THAT first.
2. **`git log -S <marker>` for your edit before re-making it** — sibling sessions run whole-tree `git add`; your uncommitted shared-file work gets swept into their commit under an unrelated message (twice observed in one week). The tree often already carries the fix.
3. **Walk the pipeline with an adversarial fixture of the EXACT reported card shape.** Find the layer where the block/field first disappears. Then root-cause the CLASS, not the instance. Known drop-layer inventory:
   - hand-maintained per-type field lists (new field = dropped field)
   - per-type switch cases whose `default` returns null (new block type = block gone)
   - TWO co-existing dataset-collection helpers drifting apart
   - non-recursive reactive-detection (nested containers evaluated shallow)
   - views re-entering a shared renderer without passing context (nested content loses the root context)
   - stale checks asserting a superseded design
4. **Fix at the layer that drops — but prefer closing the CLASS:** context via props from the root rather than recomputed per render site; fields synthesised from their data source rather than demanded of the author; near-miss key shorthands normalised at parse rather than rejected.
5. **Proof-by-reversal without reverting shared work:** `cp file file.bak` → scripted reverse patch (exact-string replaces) → run the check → `cp` back. NEVER `git checkout`/`git stash` a shared dirty tree to isolate one fix — sibling in-flight edits die with it.
6. **Ship the check:** assert-based `*.check.ts` pushing the exact reported card shape through ALL layers and asserting the RENDERED row (a sanitized-but-unrenderable shape is still a drop), plus a regression-gate manifest row. Run order: single check → full `npm run check` → build → `systemctl --user restart astra-webui.service` (dist + restart are TWO steps).
7. **Interpreter pinning matters:** run gates/checks/builds with the interpreter pinned in `astra-webui.service` (`~/.local/node-*/bin/node`) — its bundled SQLite version differs from the dnf node, and interpreter/capability checks false-fail on the wrong binary. The gate spawns children from `process.execPath`, so the entire suite inherits one engine.

## Environment hygiene in that repo

- Runtime data files (`.cache/command-registry.json`, `data/read-state.json`, `data/theme-state.json`, `data/test-ledger.jsonl`, `data/gate-ledger.jsonl`) are runtime artifacts — not committed, kept local.
- Check-hygiene laws (each learned twice): a failing check is either REPAIRED to current intent or DEMOTED to a truthful weaker assertion — never left red, never silently green. An assertion must fail when its subject is removed: no vacuous substring sweep against prose, no assert that passes on zero rows, no test matching a null object.
- One transient poll per test case, polling TERMINAL states only: near-simultaneous multi-step transitions (write→retry→done) are proven from the fixture-owning parent via request counters / attempt counts / final state — never by a child racing a transient window smaller than its poll period.
- Cross-layer schema rule: every column any module SELECTs must exist in the CREATE TABLE **and** in an idempotent `PRAGMA table_info` → `ALTER ADD` migration in the db-open function. A live db migrated by hand hides fresh-clone divergence until a check finally reaches that path.
- Server modules importing a never-shipped helper (`does not provide an export named 'X'`) are spec-consumers: complete the spec with thin awaitable adapters over the EXISTING machinery — never a second engine.
