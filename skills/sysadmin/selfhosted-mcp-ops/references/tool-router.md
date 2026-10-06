# tool-router — routing pipeline map + audit recipe

Numbers below were live-measured once; re-measure before quoting them. Every
optional stage is fail-open, so all health claims must be re-probed by
contribution, never by exit status.

## Topology
- Source of truth: `~/Work/tool-router` (git). Shim dir `~/.tool-router/` holds
  `route` + `index` two-line wrappers into `~/Work/tool-router/scripts/`.
- Code: `scripts/` ~3.3k LOC. `router_core.py` (~1.2k) = discovery, tokenize,
  BM25 `score`, RRF `fuse`, card render. `pipeline.py` = the 4 stages + per-kind
  quota. `source.py` = registry search, gap oracle, auto-install tier.
  `gaptrack.py` = state store. `rewriter.py`, `laya_rerank.py`,
  `dense_index.py`, `selftest.py`, `gate.py`, `index_build.py`.
- Index: `~/.tool-router/index.json` (~370 KB, one entry per discoverable
  capability across kinds: skill, plugin-skill, mcp, agent, command, fleet-tool,
  fleet-plugin). Dense vectors in `index.dense.npz` + `.meta.json`.
- State: `~/.tool-router/gaps.json` (intent sighting store), `sourcing.log`
  (append-only NDJSON of search / oracle / install / skip events),
  `last_route.json`, and one `breaker-*.json` per optional dependency — each
  holds `{"until": <epoch>}`; delete the file to reset.

## The four stages

1. BM25 `score` over the whole index — the only lane that must work.
2. Dense fusion: Ollama `nomic-embed-text` vectors, RRF k=60. Advisory.
3. Laya rerank of the shortlist, margin-gated against the uniform baseline
   `1/N`. Advisory. Config key is `laya_rerank.timeout_s`; there is no
   `enabled` key, so "disable" means setting the timeout to 0 or removing the
   stage call.
4. Prompt rewrite: gemini-flash then flash-lite, 12 s timeout, breaker on total
   failure. `--no-rewrite` skips it.
   Then merge: picks1 + unseen picks2, capped at N.

Wiring: Claude `UserPromptSubmit` hook runs `route.py --hook`; Hermes runs it in
the `tool-router` plugin at `pre_gateway_dispatch` with a per-session result
cache; opencode and agy get it as a prompt-level instruction block only, no
hook. A hook timeout above is the hard ceiling on how slow the pipeline may get.

## Audit recipe (the part worth repeating)

Run the pipeline, then bisect per stage inside one probe that imports the
modules rather than editing them:

```python
import time, router_core as rc, dense_index as di, laya_rerank, source
t = time.time(); rc.score(idx, prompt, stack, rc.load_learned(), cfg.get("mcp_hints")); print("bm25", time.time()-t)
t = time.time(); dh = di.dense_rank(prompt, idx, dense_path, top_n=50);      print("dense", time.time()-t, len(dh))
t = time.time(); laya_rerank.rerank(ranked, prompt, cfg);                     print("laya", time.time()-t)
t = time.time(); source.auto_install(prompt, prompt, cfg, picks);            print("source", time.time()-t)
```

Then attribute: monkeypatch `source.auto_install = lambda *a, **k: (None, {})`
and re-run the real `pipeline.run`. If wall time collapses from tens of seconds
to milliseconds, the network stage is the cost and the ranking stages are fine.

Always print `len()` of each advisory stage's return. An empty dense lane and
a tripped Laya breaker both look exactly like success from the outside.

## State-store pathologies to check for

`gaps.json` is keyed on free-text-derived tokens. Audit it for: entry count,
longest key, and sighting-count distribution. Whole-prompt dumps (system
prompts, training templates) become their own multi-thousand-character keys,
and their `count` grows without bound, which re-triggers that intent's expensive
registry search on every later call. A store that only grows and whose keys are
raw prompts is the thing to fix before adding any new capability to it.

The 30-day prune in `gaptrack.record_gap` runs on every call and rewrites the
whole file — that is fine at a few hundred entries, not at thousands.