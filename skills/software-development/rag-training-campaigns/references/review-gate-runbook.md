# Review gate runbook (neutrinos-mcp ragtrain)

Concrete commands for running the quality gate on generated question pools.
Load only when actually running the gate; the SKILL.md carries the rules.

## Emit review files

```bash
cd ~/Work/Neutrinos/neutrinos-mcp && mkdir -p ragtrain/review
for pool in train dev test-gate final-holdout; do
  python3 ragtrain/emit_for_harness.py ragtrain/datasets/$pool.jsonl ragtrain/review/${pool}_review.jsonl
done
```

Review files carry sequential ids (ragtrain-N); pool files carry UUIDs. Report
line numbers = review file positions = original pool file positions (emit
preserves order).

## Build the 10% deep sample (pre-built so the reviewer spends budget on judgment)

```python
import json, random
random.seed(7)
sample = []
for pool in ('train','dev','test-gate','final-holdout'):
    lines = [json.loads(l) for l in open(f'ragtrain/datasets/{pool}.jsonl') if l.strip()]
    k = max(1, round(len(lines)*0.10))
    sample += random.sample(lines, k)
with open('ragtrain/review/deep_sample.jsonl','w') as f:
    for q in sample: f.write(json.dumps(q, ensure_ascii=False)+'\n')
```

## Two-tier gate prompt (GLM 5.3 via opencode)

```bash
opencode run -m zai-coding-plan/glm-5.3 "<review prompt>"
```

Prompt structure that worked: (1) deep-verify deep_sample against
`data-source/cache/<pub>/<slug>.md` — span verbatim (byte, then
whitespace-normalized, then entity-normalized tiers), URLs/paths real, version
facts correct; (2) pattern-scan 100% — duplicates, banned phrases,
double-barreled, doc-artifacts, version contamination; (3) write report with
per-pool PASS/FAIL, counts, exact records to remove (pool/line/excerpt/reason),
GO/NO-GO.

Required opencode.json allowlist before a headless run (print mode auto-rejects
'ask' commands):

```json
"bash": { "head *": "allow", "wc *": "allow", "grep *": "allow",
          "find *": "allow", "sed *": "allow", "ls *": "allow" }
```

Model verification: grep `~/.local/share/opencode/log/opencode.log` for the
session id, count `providerID=`/`modelID=` occurrences — confirms which model
actually served the calls and catches small_model leaking to ollama.

## Removal from pools (after the gate)

Parse the report tables (pool -> line -> reason), then remove pool records BY
POSITION (report line = review line = pool position). Never remove by
chunk_id — multiple questions share chunks. Assert removed count == expected
before writing. Keep the removed records in `regen_<pool>.jsonl` for
regeneration.

WARNING: `validate_datasets.py build` regenerates `datasets/<pool>.jsonl` from
`gen_out/<pool>/` batch files — removals applied directly to the pool output
files are silently undone by the next build. Apply removals AND regeneration
merges to the `gen_out` source batch files, then run build. Also verify the
build result matches expectations afterwards: a stale-build reading (build
report shows old counts) means the build read source files that no longer
reflect your removals.

## Span-level dedupe (new gate-mandated stage)

Sibling-version docs repeat sentences verbatim, so byte-identical answer spans
appear across pools (37 cross-pool leak groups in one gate pass) and within a
pool (up to 3 questions on one span). Run this AFTER all generation and BEFORE
pool splitting / gate:

```python
# normalize whitespace+case, group by span, keep one per group;
# on cross-pool groups keep the most held-out copy (final-holdout > test-gate > dev > train)
priority = {'final-holdout': 0, 'test-gate': 1, 'dev': 2, 'train': 3}
span_map = {}
for pool in ('train','dev','test-gate','final-holdout'):  # ascending priority order
    src = f'ragtrain/datasets/{pool}.jsonl'
    records = [json.loads(l) for l in open(src) if l.strip()]
    keep = []
    for r in records:
        s = ' '.join(str(r.get('answer_span','')).split()).lower()
        if s in span_map and priority[span_map[s]] <= priority[pool]:
            continue  # existing copy is in a more held-out pool; drop this one
        span_map[s] = pool
        keep.append(r)
    open(src, 'w').write(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in keep))
```

version_pinned is special: the gate requires the pinned answer to NOT appear
in the sibling-version publication at all — generate with a prompt banning
URL/path/image answers and rejecting candidates whose span exists in the twin
version. Expect near-zero survivors from a naive pass; regenerate, don't
hand-patch.

## Deep span verification tiers (in acceptance order)

1. byte-verbatim containment
2. whitespace-normalized containment
3. entity-normalized containment (reported separately)

Manually adjudicate heuristic 'ungrounded' verdicts: version numbers inside
the doc's own example commands, ports (8083), platform URLs are false
positives; ~1/3 of regex hits are false positives.
