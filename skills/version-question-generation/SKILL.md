---
name: version-question-generation
description: Generate version-pinned and version-agnostic questions via GLM 5.3 on Z.ai coding endpoint for neutrinos-mcp RAG training pipeline
category: rag-development
---

## Triggers
Use when generating version-contrast questions for RAG training datasets via GLM 5.3 on Z.ai API. For neutrinos-mcp project, version-divergent chunks require twin-group question generation.

## Always-on Rules
1. Z.ai coding endpoint only: https://api.z.ai/api/coding/paas/v4/chat/completions. General endpoint /api/paas/v4/ returns error 1113 even with $80 coding pro subscription.
2. Thinking param mandatory: must include "thinking": {"type": "enabled"} in every request body. Missing this causes error 1210.
3. Rate-limit ceiling: ~3 batches/10min max throughput regardless of parallel workers. All 195 vc batches require ~10-12h minimum.
4. Priority processing: train+test-gate pools (116 batches, 923 version-divergent chunks) first — these feed the training loop.
5. Resumable generation: workers self-skip completed batch output files (vcNNNN.jsonl exists + non-zero size).
6. Validator integration: output passes same validator as main corpus; rejections are genuine quality issues.
7. Key file never commit: ~/.config/neutrinos-mcp/zai_key local-only, never committed to repo.

## Procedures

### Step 1: Verify Z.ai configuration
```bash
cat ~/.config/neutrinos-mcp/zai_key
curl -s -m 180 https://api.z.ai/api/coding/paas/v4/chat/completions \
  -H "Authorization: Bearer $(cat ~/.config/neutrinos-mcp/zai_key)" \
  -H "Content-Type: application/json" \
  -d '{"model":"glm-5.3","messages":[{"role":"user","content":"Say test"}],"thinking":{"type":"enabled"},"max_tokens":20}'
```

### Step 2: Check current state
```bash
cd ~/Work/Neutrinos/neutrinos-mcp && \
  echo "vc batches: $(ls ragtrain/datasets/gen_out/vc/*.jsonl 2>/dev/null | grep -c jsonl)/195" && \
  echo "vc questions: $(cat ragtrain/datasets/gen_out/vc/*.jsonl 2>/dev/null | wc -l)"
```

### Step 3: Launch workers
```bash
cd ~/Work/Neutrinos/neutrinos-mcp
for i in 1 2 3 4; do
  python3 ragtrain/vc_worker.py w$i $(( (i-1)*25 )) &
done
wait
```

### Step 4: Or use priority worker for train+test-gate first
```bash
cd ~/Work/Neutrinos/neutrinos-mcp
python3 ragtrain/vc_priority_worker.py pw0 0 &
# Monitor progress
watch -n 60 'cd ~/Work/Neutrinos/neutrinos-mcp && echo "vc: $(ls ragtrain/datasets/gen_out/vc/*.jsonl | grep -c jsonl)/195 batches, $(cat ragtrain/datasets/gen_out/vc/*.jsonl | wc -l) questions"'
```

### Step 5: After all 195 batches done → final validation
```bash
cd ~/Work/Neutrinos/neutrinos-mcp && python3 ragtrain/validate_datasets.py check
```

## Pitfalls

**Pitfall: 12-parallel-worker illusion**
- Rule: Do not launch more than 6 parallel GLM 5.3 workers. Z.ai serializes beyond small per-session cap; excess workers queue and wait, adding latency without throughput gain.
- Why: Z.ai imposes per-minute request limits per API key/session at the service layer, not client layer.

**Pitfall: Omitting thinking param**
- Rule: Always include "thinking": {"type": "enabled"} in every GLM 5.3 request body. Missing this causes error 1210.
- Why: GLM 5.3 on coding endpoint requires thinking configuration; cannot be disabled.

**Pitfall: Assuming main corpus generation pattern applies**
- Rule: VC generation uses a different prompt (version_contrast.md) and batch structure (vc_batches/vcNNNN.json) than main corpus question generation. Do not reuse gen_questions.py flow without adapting the prompt and validator.
- Why: Version-divergent chunks require twin-group mining (version_pinned + version_agnostic facets); the prompt and output schema are fundamentally different.

**Pitfall: Not checking completed output before assuming failure**
- Rule: Before blaming a worker crash, verify which batches are done: ls ragtrain/datasets/gen_out/vc/*.jsonl | grep -c jsonl. Workers self-skip existing output files; a partial file may mean some batches completed successfully.
- Why: Resumable design means partial progress is preserved; re-running from scratch wastes hours.

## References

### references/zai-key-setup.md
```markdown
Z.ai API key setup for GLM 5.3 coding endpoint

Location: ~/.config/neutrinos-mcp/zai_key

Contents: Raw API token string (never commit to repo)

How to obtain:
1. Subscribe at https://www.z.ai (80-dollar coding pro tier)
2. Generate token from dashboard
3. Store at ~/.config/neutrinos-mcp/zai_key — read-only by gen_scripts

Verification:
```bash
cat ~/.config/neutrinos-mcp/zai_key | head -c 20
# Then test:
curl -s https://api.z.ai/api/coding/paas/v4/chat/completions -H "Authorization: Bearer $(cat ~/.config/neutrinos-mcp/zai_key)" ...
```
```

### references/batch-structure.md
```markdown
VC batch file format: ragtrain/datasets/vc_batches/vcNNNN.json

Each file contains JSON array of objects with fields:
- chunk_id: unique identifier
- product: publication name
- version: doc version (e.g. 7, 8, 9)
- version_div: boolean, True if content differs across versions
- text: the chunk content to generate questions from
- heading_path: documentation path

Output: ragtrain/datasets/gen_out/vc/vcNNNN.jsonl
Each line is a generated question JSON with fields:
- question_type: "version_pinned" or "version_agnostic"
- question: the generated question text
- chunk_id: links back to source
- product, version: metadata
```

### references/op-route-debug.md
```markdown
GLM 5.3 endpoint routing debug

Observed error sequence when using wrong config:
1. General endpoint /api/paas/v4/ → error 1113 (Insufficient balance) — even with $80 coding pro subscription
2. Coding endpoint without thinking param → error 1210 (Thinking parameter required)
3. Coding endpoint WITH thinking:{"type":"enabled"} → works (returns response)
4. glm-4.5-flash on coding endpoint → empty responses for large prompts (>60k chars)

Fix verified: Use coding endpoint https://api.z.ai/api/coding/paas/v4/chat/completions with glm-5.3 model and thinking:{"type":"enabled"} param. Subscription balance lives on this endpoint only.
```

## Scripts

### scripts/gen_vc_priority.sh
```bash
#!/usr/bin/env bash
# Launch priority VC workers for train+test-gate pools only
cd ~/Work/Neutrinos/neutrinos-mcp
python3 ragtrain/vc_priority_worker.py pw0 0 &
python3 ragtrain/vc_priority_worker.py pw1 15 &
python3 ragtrain/vc_priority_worker.py pw2 30 &
python3 ragtrain/vc_priority_worker.py pw3 45 &
wait
echo "Priority VC generation complete"
```

### scripts/check_vc_progress.sh
```bash
#!/usr/bin/env bash
# Quick progress check for VC generation
cd ~/Work/Neutrinos/neutrinos-mcp
echo "VC batches done: $(ls ragtrain/datasets/gen_out/vc/*.jsonl 2>/dev/null | grep -c jsonl)/195"
echo "VC questions generated: $(cat ragtrain/datasets/gen_out/vc/*.jsonl 2>/dev/null | wc -l)"
echo "Remaining priority: $((116 - $(ls ragtrain/datasets/gen_out/vc/vc*.jsonl 2>/dev/null | while read f; do [ -f "$f" ] && echo 1; done | sort -u | wc -l)))"
watch -n 60 ./scripts/check_vc_progress.sh
```