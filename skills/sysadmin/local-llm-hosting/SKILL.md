---
name: local-llm-hosting
description: Use when choosing or serving a local LLM on kurama-core.
version: 1.0.0
author: kurama-core
license: MIT
hermes:
  tags: [llm, llama.cpp, local-inference]
  related_skills: [huggingface-local-models, gguf-quantization]
---

# Local LLM hosting on kurama-core

## When to Use
Any request involving a locally hosted LLM on this desktop: model selection research, context-window fit checks, quantization choice, serving config, speculative-decoding setup, tok/s projections, or fine-tuning plans. Also applies when a locally hosted model backs another project (e.g. trading-bot classifiers).

## Hardware envelope (verified 2026-10-05)
RTX 4070 Ti SUPER 16GB (672 GB/s), 64GB DDR5 (~39GB free), i7-14700K, NVMe `/home` — check disk (`df -h`) before any model download; at ~24GB free it is routinely the binding constraint. List cleanup candidates for the user, never auto-delete.

## Research workflow (in this order)
1. Verify hardware live (`nvidia-smi`, `free -h`, `df -h`), never from memory.
2. Compute KV-cache fit programmatically (execute_code), not by estimating: `KB/tok = 2 * layers * kv_heads * head_dim * bytes_per_val`. Test each candidate at target contexts; mark FIT vs split vs OVER against a ~14.5GB usable-VRAM budget or weights+KV totals vs free system RAM.
3. Pull official HF model cards for native context and serving limits — vendor cards state the real VRAM floor for their max-context claims; cross-check third-party fit tables (modelanatomy/modelfit) for per-quant file sizes.
4. Read llama.cpp docs + recent PR/issue trails for the architecture (MoE offload, spec-decode support, MTP) — blog numbers age fast, mainline changes monthly.
5. Present findings with every tok/s figure labeled PROJECTED vs MEASURED-ON-COMPARABLE-HARDWARE; close with a live `llama-bench` on this card as the required confirmation step.
6. Run done_gate over claims vs evidence before delivering a recommendation.

## Fit rules (compute, don't guess)
- Context memory is the killer, not weights: on a 30B-A3B (48 layers, 4 KV-heads, 128 dim) q8 KV costs ~1.5GB per 64K tokens; a 14B dense with 8 KV-heads costs 2x that. A '1M context' marketing claim means nothing without the KV math — vendor cards that quote 1M also quote a server-class VRAM floor; quote both to the user.
- MoE models are unusually quant-tolerant (dormant experts never fire; ~0.15 PPL delta Q2_K vs Q8 on 80B MoE). Aggressive quants (IQ3_XXS, Q4_K_S) are near-free on MoE; do NOT transfer this reasoning to dense models.
- Weights file that leaves ~1.5GB for KV keeps ~64K context in-VRAM; beyond that, offload MoE experts to system RAM (`--n-cpu-moe N`) — trades ~20-30% speed for large context; probe the n-cpu-moe count by trial.

## Speed stack, ranked by measured impact
1. Pick a MoE with small active params (3B of 30B) first — architecture choice beats every inference trick.
2. Speculative decoding (lossless by construction): EAGLE3 draft reads target hidden states, 2-4x on code; n-gram lookup drafters cost zero VRAM/model and stack on top (up to ~4.7x on code-heavy turns). Draft under ~1/3 of target size, same tokenizer family mandatory, temperature <=0.2.
3. q8_0 KV cache with `--flash-attn on` — halves KV memory, ~free quality.
- Pitfall: acceptance collapses past a few thousand output tokens and past batch ~16-32 (spec-decode actively slows long-context and batched workloads). Enable for interactive code edits only; leave off for long-form generation and parallel/batched jobs.
- Pitfall: an n-gram drafter drafts re-emitted text — it inflates code-rebuild sessions but harms prose/creative output. Profile per workload, not per model.
- Embedding/summarization traffic gains nothing from spec-decode; batched offline jobs should use plain decode instead.

## Serving (llama.cpp is the engine on this host)
Build CUDA from source for current kernels; serve with OpenAI-compatible `llama-server -ngl 99 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0`; EAGLE3 adds `-md <draft.gguf> --spec-type draft-eagle3 --spec-draft-n-max 8`. Single-user desktop = llama.cpp over vLLM (vLLM's batching advantage is irrelevant at batch 1 and it carries more VRAM overhead).

## Fine-tuning on own code
QLoRA via Unsloth on a 30B MoE fits a 24GB GPU with LoRA-adapter training only; sequence = repo slices -> QLoRA -> merge -> re-quant GGUF. Honest framing: fine-tune teaches conventions/format, never expands context — long-context ability comes from base model YaRN + serving flags.
