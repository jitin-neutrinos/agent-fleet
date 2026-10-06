# Laya edge variant — size/latency math and build path

## The constraint band

Target: decision-model under 100 MB resident, sub-100 ms per scoring call,
CPU-only (no daemon reservation; loads, scores, unloads).

## Measured math (params × precision)

| variant | params | bits | size |
|---|---|---|---|
| fp32 | 421M | 32 | 1.6 GB (the full checkpoint) |
| fp16 | 149M | 16 | ~284 MB |
| int8 | 149M | 8 | ~142 MB (marginal — over the line) |
| int4 | 149M | 4 | ~71 MB ✓ |
| int8 | 395M | 8 | ~377 MB ✗ |

So: the base encoder at int4 is the only shape under 100 MB with headroom.
ModernBERT-base is 149M params (22 layers), Apache-2.0; the decision-head
sequence is short (192 tokens), which is what makes CPU latency feasible —
single-thread runs ~30–60 ms at that length, and the host has 28 threads.

## Build path (proven recipe, not yet run to completion)

1. **Distill**, not retrain: the production checkpoints are ModernBERT-large
   + LoRA decision head; the behavior to copy is the head's decision
   distribution over candidate sets. Train a base-size student against the
   teacher's outputs on the mined gate/routing dataset (the training pipeline
   already carries the LoRA-r16-alpha32 recipe and the dataset).
2. Export ONNX; int4/dynamic-quantize; assert the artifact size < 100 MB and
   measure p50/p99 latency at 192 tokens before wiring it anywhere.
3. Wire as an OPTIONAL lane behind config + a file-existence check (the
   distilled checkpoint on disk = lane armed; absent = gracefully off), the
   same fail-open shape as the dense lane. Never a hard dependency.
4. Validate scoring agreement against the server engine on the golden set
   before trusting its verdicts in any gate (risk/HITL roles stay with the
   server-side engine until the edge model proves parity).

## Boundary

The edge variant is a scorer for cheap inline decisions (rerank, tier snaps).
Anything security-relevant or irreversible keeps the full engine — a 4-bit
student has not earned gate authority.
