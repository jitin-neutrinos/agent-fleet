# Local edge-model service pattern (compression scorer, memory daemon)

Shape for any always-available-but-lightly-loaded local model service: the user wants
sub-second analysis when context arrives, minimal resident footprint the rest of the time,
and no degradation of the main agent when the service is down.

Two proven consumers of the pattern: a compression scorer layer and a tool-selection
layer (retrieval rerank + dynamic top-K). Both ride ONE socket-activated daemon with one
endpoint per lane (`/score`, `/gate`, `/rerank`, `/toolrank`) — do not spawn a second
daemon for a second consumer; add a lane.

## Model selection for retrieval/rerank lanes (measured)

- **Small cross-encoders beat large instruction rerankers on domain niches** — a 109M
  ListNet-fine-tuned cross-encoder outscored a 4B instruction reranker; niche selection
  rewards specialization over size. Keep rerank candidate sets ≤20 — cross-encoder cost
  is super-linear in list size.
- **Rerankers that score by yes-token probability (causal-LM style) are NOT drop-in** on
  llama.cpp/Ollama native rerank endpoints — those toolchains mis-score them today; serve
  them through vLLM/transformers or a custom chat-template scorer, and pin the runtime
  version in the lane's config.
- **Query instructions matter (1–5% on trained retrievers)** — pass a task-tuned
  instruction on the query side; English instructions even for multilingual corpora.
- **Tool/doc retrieval is its own niche, not generic IR** — off-the-shelf embedding
  models score poorly on tool corpora (best general retrievers ≈ 34 nDCG@10 on the big
  tool-retrieval benchmarks); expect to enrich documents (when-to-use/not-for/tags
  generated offline) before retrieval quality is usable, and treat that enrichment as
  the cheapest single quality lever.

## Lifecycle contract

- **systemd socket activation** (or a single resident daemon when it must tail streams):
  zero resident when idle; first request triggers load. `MemoryMax=<cap>` (e.g. 3–4G)
  cgroup-enforced.
- **Idle unload**: timer drops the model and exits; weights stay in page cache so warm
  re-init is sub-second. Never OOM the host to stay warm.
- **Queued, batched work**: one worker, mpsc queue, batch window (e.g. 50ms–2s) per
  request. Backpressure returns `busy` and the caller falls back — never block a turn.
- **Fail-open**: service down = caller uses the deterministic/heuristic path. Same
  contract as guardrail layers; a dead scorer must never dead-agent.

## Wire protocol

Unix-socket JSON, one endpoint per capability: `/score`, `/gate`, `/rerank`. The consumer
(the compressor, the memory daemon, the agent) is just another client — no in-process
coupling. Quantized models only (int8/int4 ONNX via `ort`); record measured p50/p99 and
peak RSS in the project ledger.

## Model selection (validated on ~4GB budget)

| Role | Model | Resident | Latency |
|---|---|---|---|
| token keep/drop + self-information | Qwen2.5-0.5B-Instruct int4 | ~1.5GB @4k ctx | ms/segment |
| query-aware relevance | ms-marco-MiniLM-L-6 cross-encoder int8 | ~90MB | ~tens of ms/pair (Rust ONNX p99 36ms) |
| decisions/gates | local decision model (laya int8) | ~18MB | ~40ms/decision |
| zero-shot NER | GLiNER-small v2.5 edge int8 | ~60MB | ms/segment |
| relations | GLiREL | ~120MB | shares session |

Small guards beat big ones on robustness benchmarks (1B > 8B on attack sets) — small is
both cheaper and better for classification-shaped work.

## Benchmark gating

Optimizations earn defaults only through a bench on REAL data (production transcripts,
not synthetic fixtures): the metric pair that decides is effect-size vs regret (e.g.
≥25% token reduction at ≤2pp quality delta). Latency + RSS are recorded, never the sole
gate. Every number lands in the ledger row for the arc.
