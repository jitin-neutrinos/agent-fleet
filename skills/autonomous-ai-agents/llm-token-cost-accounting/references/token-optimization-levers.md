# Token-optimization levers — what cuts spend without cutting quality

Condensed from provider docs + 2026 research (links at the end). Ordering rule:
**structural levers first** (model sees identical input, output unchanged or
discounted), **lossy levers only where benchmarks show <2% deltas or the raw
text stays recallable**.

## 1. Provider prompt caching (structural, zero quality risk)

| Provider | Enable | Read mult | Write mult | Break-even reuse |
|---|---|---|---|---|
| Anthropic | explicit `cache_control` breakpoints (≤4) | 0.1x | 1.25x (5-min) / 2x (1-hour) | ~1.28 (5-min pays off on 2nd request) |
| OpenAI ≥ GPT-5.6 | automatic (+ optional breakpoints) | 0.1x | 1.25x | ~1.28 |
| OpenAI older | automatic | up to 0.1x | free | 1.0 — always wins |
| Gemini 2.5+ | implicit; explicit optional | ~0.1x | free implicit; explicit $/MTok/hr storage | watch storage |
| DeepSeek | automatic, always on | ~0.03–0.1x | none | always wins |

Traps: (a) one changed character before the breakpoint voids the ENTIRE cache
silently; (b) Anthropic's 1-hour tier costs MORE than no caching below ~67%
hit rate (2x write premium) — 5-min refreshes free on use; (c) caching
discounts INPUT only, output bills full — pair with terse-output mandates;
(d) Haiku-class models carry the HIGHEST minimum prefix (4,096).

**Prove it hit** via response usage fields, logged per task not globally:
Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens`; OpenAI
`cached_tokens`; Google `cachedContentTokenCount`; DeepSeek
`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`. A zero read field over
a stable-prefix workload = silent miss. Target 60–80% hit rate.

## 2. Batch / Flex (structural — quality identical, latency traded)

OpenAI Batch + Anthropic Message Batches: flat **50% off input AND output**,
higher rate limits, ≤24h SLA (often ~1h). Fit: nightly evals, golden-set
runs, bulk doc processing, A/B prompt tests — never interactive chat.

## 3. Compaction / context management (measured, can IMPROVE quality)

- Acon (arXiv 2510.00615): 26–54% fewer peak tokens WITH higher task success;
  optimizes compression guidelines in natural language, model-agnostic,
  distills to small compressors retaining ~95%.
- ACM (arXiv 2607.23809): agent-initiated manage_context/query_memory tools,
  raw history kept on disk = lossless recall; ~20% peak reduction, +8–27%
  benchmarks.
- TRACE (arXiv 2608.06503): naive recurrent compression WEAKENS recent-state
  influence → blocked actions, repeated exploration. Never blind-truncate
  agent history; use guided/structured summarization.
- Structured > freeform summaries (Factory probe: 3.70 vs 3.44 default vs
  3.35 opaque). Proactive compaction at ~70% utilization beats reactive at
  95%.

## 4. Prompt compression (lossy, bounded)

LLMLingua/LongLLMLingua (microsoft/LLMLingua): up to 20x on static prompts,
~4x long context, <2% benchmark loss at moderate ratios; LongLLMLingua showed
+17.1% at 4x (noise filtering). Use on reference docs/skill bodies, never
live agent state. AutoCompressors/Gist/ICAE need fine-tuning — skip for
API-model setups.

## 5. Routing / tiering + output controls

Biggest lever after caching; quality guarded by routing correctness gates
(adoption floors, abstention). Output-side: max tokens, terse modes,
reasoning-effort pinned per tier (premium for judgment, cheap for mechanics).

## Sources

- https://intuitionlabs.ai/articles/llm-prompt-caching-cost-savings
- https://digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide (hit-rate economics matrix)
- https://mixroute.ai/blog/prompt-caching-guide (usage-field verification, DeepSeek 50x)
- https://developers.openai.com/api/docs/guides/batch
- https://dev.to/mukundakatta/when-and-how-to-use-the-anthropic-batch-api-in-your-agent-5fgn
- https://arxiv.org/html/2310.05736v2 (LLMLingua)
- https://arxiv.org/html/2510.00615v3 (Acon)
- https://ar5iv.labs.arxiv.org/html/2607.23809 (ACM)
- https://arxiv.org/pdf/2608.06503 (TRACE)
- https://github.com/redhat-ai-americas/memory-hub/blob/main/research/context-compaction-survey.md
