---
name: esm-ts-testing
kind: reference
scope: agentive-pipeline test phase (any repo with .ts ESM test files)
---

# `.ts` ESM test files — `node --test` fails, `tsx --test` works

**Pitfall:** In a `"type":"module"` repo with `.check.ts` test files (`canvas-schema.check.ts`, etc.), bare `node --test src/lib/file.check.ts` fails with `ERR_MODULE_NOT_FOUND` because ESM requires `.js` extensions in the import spec; TypeScript source does not resolve. This costs a turn if you assume `node --test` works and try to debug the module graph.

**Fix:** Always use `npx tsx --test <file>` for `.ts` ESM tests. Confirmed working on `astra-webui/src/lib/canvas-schema.check.ts` (11 tests pass). Never try to fix import extensions manually — that's not the bug; the runner is wrong.

**Verification pattern (leave behind):**
```bash
npx tsx --test src/lib/<name>.check.ts 2>&1 | tail -5
```
If it reports `ok N - ...` / `pass N / fail 0`, the canvas/test pipeline is sound. If it reports `ERR_MODULE_NOT_FOUND`, the runner (not the code) is the issue.
