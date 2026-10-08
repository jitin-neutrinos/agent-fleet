# Token-optimization levers — what cuts spend without cutting quality

Condensed from provider docs + 2026 research (links at the end). Ordering rule:
**structural levers first** (model sees identical input, output unchanged or
discounted), **lossy levers only where benchmarks show <2% deltas or the raw
text stays recallable**.

## 0. Decision table — adopt vs skip (added from the 2026 survey pass)

| Lever | Saving | Quality risk | Verdict |
|---|---|---|---|
| Provider prompt caching (§1) | up to ~90% on repeated prefix | zero | adopt |
| Batch/Flex (§2) | flat 50% both directions | zero (latency only) | adopt for evals/nightly |
| Context editing / stale tool-result clearing | Anthropic measured −84% tokens, +29–39% accuracy in 100-turn agentic search | none measured | adopt (Claude platform: `clear_tool_uses_20250919`; SDK compaction covers the rest) |
| Anthropic 1-hour cache tier | cheap on high hit rates | zero | adopt ONLY at ≥67% hit rate — below that the 2× write premium loses money vs 5-min refreshes |
| Sub-agents / just-in-time context | large (summaries only in parent) | low | default architecture |
| Online KV compaction (TokenPilot-class) | 56–87% in papers | low with delayed eviction | n/a for API harnesses; vLLM-class self-serving only |
| Model routing / cascades (RouteLLM) | 2×+ | real: "quality parity" = 90–95% | skip as automation; manual tiering (premium for judgment, cheap for mechanics) is the safer version |
| Semantic caching (GPTCache/LiteLLM) | 25–40% of traffic | HIGH: published tables show 3–7% of hits are confidently WRONG at sane thresholds; near-identical phrasings collide at 0.91 similarity | skip for coding/agent workloads (hit rate only 20–30% there anyway); if ever used: threshold ≥0.95, short TTL, exact-match only for anything stateful |
| LLMLingua-class prompt compression | up to 20× static prompts | moderate; never on live agent state | reference docs only (§4) |

Unifying research anchor: the rate–distortion compaction survey — irreversible
summarization compounds errors on every re-compaction, while reversible
operators (archive original + retrieve on demand) hold accuracy indefinitely.
Prefer reversible-by-design levers (external files, scratch notes, memory
stores) over aggressive summarization. TokenPilot adds: compact on a delayed
schedule using the agent's own future queries as the signal, never immediately.

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
- https://www.anthropic.com/news/context-management (context editing + memory tool; −84% / +accuracy data)
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context (tool search vs caching vs context editing decision table)
- https://www.alphaxiv.org/abs/2607.08032 (rate–distortion compaction survey: irreversible vs reversible)
- https://arxiv.org/pdf/2608.00902 (online KV compaction: delayed proxy queries beat immediate)
- https://arxiv.org/html/2406.18665 (RouteLLM: 2× at ~90% quality — read the caveat, not the headline)
- https://dev.to/dublecc/semantic-caching-for-llm-apis-how-similarity-based-response-caching-actually-works-1gkg (threshold/false-positive tables)
