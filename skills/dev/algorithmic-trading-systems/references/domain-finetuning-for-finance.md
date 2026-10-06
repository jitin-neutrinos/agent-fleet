# Domain fine-tuning for a trading system — methods, data, and the trap

For the request "fine-tune our analysis models on institutional papers, arXiv
and financial data." Read this before scoping the work. The methods are
ordinary; the trap is not, and it is the part that decides whether anything you
build is worth anything.

## The trap, stated first

**Training on the literature that describes a method, then testing that method,
manufactures a result.** A model fine-tuned on papers about momentum, or
trend-following after financing, or sentiment-driven gold returns, has been
fitted to the method's description. Evaluating it on that method is a memory
test. The result will be strong, will replicate, and will mean nothing.

The critical structural point: **this is not fixed by held-out splitting.** The
contamination enters at *training* time, so your test set is clean and your
number is still false. Every other contamination defence in
`references/backtest-validity.md` operates at evaluation time and none of them
touch this. It is also undetectable by auditing the data pipeline — the
training corpus looks exactly like the training corpus you meant to use.

So when a user asks to fine-tune on papers in order to get better trading
results, the honest first response is to name this, then offer the paths that
do work:

1. **Fine-tune for capability the base model lacks** — classifying event type,
   extracting structured fields from filings, scoring a defined label — rather
   than for a signal you intend to trade. This is legitimate and useful.
2. **Fine-tune on data that post-dates the model's cut-off**, then evaluate only
   on periods after that boundary. Pick the training window so it cannot
   contain the test window's method descriptions.
3. **Prefer RAG over fine-tuning for domain knowledge.** Retrieving a paper at
   inference keeps the weights clean, keeps the citation attached to the claim,
   and means a new paper does not require a retrain. For a corpus that is
   written evidence, this is almost always the better engineering choice.
4. **Use a labelled finance corpus for the classifier**, not papers. The
   objective is well-defined and the benchmark exists.

What is not legitimate: fine-tune on papers describing strategy *S*, then report
that the model predicts *S* well, as evidence that the approach works.

## Label maturity before training

Inherited from `references/self-improving-agent-loops.md` and worth restating
because it bites fine-tuning specifically: a label that has not matured is not a
negative example. If you train on labels resolved before their holding window
traded, the model learns from outcomes that were not knowable at decision time.
For delayed outcomes, use a library that ships a simulate-with-delay helper
rather than hand-rolling it, and never resolve early to get more rows.

## What fine-tuning is actually good for here

Be concrete about the objective, because the difference is the whole argument:

- **Event classification** — is this release hawkish or dovish, which variable
  moved, is this filing material. A defined label, a real benchmark, and it is
  defensible to train.
- **Field extraction from unstructured text** — pull the instrument, the
  direction and the size out of prose. The model is doing extraction, not
  prediction.
- **Reasoning style and format adherence** — teaching a small model your output
  schema and your conventions reliably. Low risk, real benefit, no contamination
  concern because the target is format rather than a market claim.
- **Domain language comprehension** — continued pretraining on finance prose
  can genuinely help comprehension of filings and jargon.

What it is not good for: predicting returns, timing entries, or beating a
rules-based baseline. If the claim is directional and the training data is
unlabelled market text, the honest answer is that nobody has shown this works
reliably, and the burden of proof is on the backtest clearing a rules baseline
after costs.

## The overfitting floor for any fine-tuned model

Whatever the task, the trial-count discipline from
`references/backtest-validity.md` applies unchanged, and fine-tuning makes it
worse — a fine-tuning run is itself many trials. Sweep size, learning rate,
rank, epoch count and seed are each a trial. Record them.

Run the control: the same pipeline on an instrument where the effect is known to
exist and one where it is not. If both return the same verdict, the harness is
rubber-stamping and every result from it is void.

## Sizing a fine-tuning job honestly

Before quoting a time or a feasibility claim, check free disk, free VRAM and the
existing cache. Two things routinely bite:

- **Check what is already cached** before downloading a model. A domain
  classifier may already be in the local model cache from unrelated work, and
  re-fetching it wastes both disk and time on a machine that may be near full.
- **Disk is a real constraint for training.** Fine-tuning adds checkpoints,
  datasets and a working copy on top of an existing model cache. Check free
  space and offer to reclaim before starting, not after the failure.
- **`df -h /home` is the wrong question on this box.** `/home` (nvme0n1p6, btrfs)
  really is often at 92% with only ~39 GB free — and reading that as "we must
  delete something first" is wrong. Measured 2026-10-04 with `lsblk` + `df -hT`:

  | Mount | Device | Free | Role |
  |---|---|---|---|
  | `/mnt/work` | nvme1n1p1, ext4, **916 GB** | **613 GB** | Fast NVMe — **the training drive**. Already has `datasets/`, `models/`, `projects/`, `backups/` |
  | `/mnt/hdd-storage` | sda1, NTFS, 1.9 TB | 1003 GB | Cold bulk archive |
  | `/home` | nvme0n1p6, btrfs, 464 GB | ~39 GB | OS + code, keep lean |

  `/mnt/work` is not mounted from `/` and is easy to miss in a casual `df` — it
  looks unused in a first pass because `lsblk` shows `nvme1n1` with no entry
  under `/`. A 7–8B QLoRA needs ~30–60 GB; that is 10× available, and it is
  NVMe, so dataset read speed (the usual training bottleneck) is not one. So: run
  `lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT` **and** `df -hT` before raising a disk
  alarm, and prefer `/mnt/work` for datasets and checkpoints. Only if `/mnt/work`
  is genuinely full is `/home` reclaim worth doing — `~/.hermes/cache` (idle-
  pruned after 24h) and `~/Work/scratch` are the honest targets, not the 15 GB
  model cache you are about to need.

Run a **CPU-only feasibility probe** before assuming a GPU is required. Many
finance classifiers and small instruct models are fast enough on CPU for a
nightly batch job. Conversely, confirm the runtime actually offloads before
promising GPU numbers — see the latency reality check in
`references/model-layer-boundaries.md`.

### Measured on kurama-core (RTX 4070 Ti SUPER, 16 GB) — use these, don't re-derive

Proven 2026-10-04 with a real training run, not an estimate. Stack: torch
2.11.0+cu128 / CUDA 12.8 / PEFT 0.21.2 / transformers 5.18.0 / bitsandbytes
0.50.2, compute capability (8, 9).

| Config | seq 512 | seq 1024 | seq 2048 |
|---|---|---|---|
| Llama-3.2-1B bf16 LoRA r16 | 4.23 GiB | 6.01 GiB | 9.58 GiB |
| Qwen2.5-7.6B dense NF4 QLoRA | 7.89 GiB | 10.12 GiB | **OOM** |
| Full fine-tune 7–8B | ~112 GB needed — impossible | | |

Throughput on the 1B run: 3,932–4,922 tok/s, so a 500k-example LoRA costs
**11 min (1B) to 40 min (7B)**. Compute is genuinely not the bottleneck — a
hundred hyperparameter sweeps cost less than a lunch. **Never present "is
16 GB enough?" as an open question on this box; it is answered.** Full
fine-tune of a 7–8B is the only genuinely impossible option here.

Watch the packaging name: the package is **`axolotl`**. `axolestr` does not
exist (PyPI 404).

## The specific licence traps, named

Not a general "check the licence" — these were each read from the provider's own
terms on 2026-10-04 and each forbids the obvious plan:

| Source | What it actually says |
|---|---|
| WRDS | "Loading Data retrieved from WRDS into LLMs is prohibited." The exception list covers CRSP/LSEG/MSCI/S&P but **excludes TAQ and Compustat** |
| FRED | 2024 ToS **explicitly bans ML training** (data retrieval itself is fine) |
| SSRN | Personal Use Only |
| NBER | Copyright stays with the authors |
| Polygon, Alpha Vantage | Non-commercial by default |
| Kenneth French | Cleanly permissive |
| arXiv REST API | **Returns no licence field at all** — see the `arxiv` skill; use OAI-PMH |

So the free-and-obvious market-data path is closed for training. Note the
distinction: FRED *retrieval* is fine (and it is the best-verified macro source
in the macro-data reference), it is *training on the retrieved series* that the
ToS forbids. Do not let a clean data pipeline smuggle a licence violation into a
training set.

## Verify a model or dataset exists before planning around it

The finance-model list is full of phantoms. Confirmed against the Hub API on
2026-10-04: **BloombergGPT was never released** (PIXIU states it explicitly);
`Open-FinLLMs/FinLLaMA` is not on the Hub at all; the
`AI4Finance-Financial-Datasets` repo every FinGPT doc links to is not public; and
the ProsusAI org has exactly **one** public model, so every `finbert-tone` /
`finbert-esg` reference is a phantom. FLARE is a benchmark and DARE is a method,
not models. What genuinely downloads: the FinBERT family, FinTwitBERT, the
FinGPT LoRA adapters, FinMA-7B.

Check the Hub (or the vendor's own index) before writing a plan that names a
model. This is the same trap as the star-count false positive in `SKILL.md`,
one layer down: the repo is cited everywhere and does not exist.

## Your own transcripts are a domain corpus with a specific risk

Agent transcripts are a legitimate source of domain-flavoured text and a real
one. Before using them, count what fraction is actually on-topic — a general
engineering transcript corpus may be a few percent relevant content in a large
volume of unrelated material, and training on the whole thing teaches the model
nothing about the domain while burning the budget.

The risks are specific and documented: training a model on its own outputs
amplifies its existing errors, can collapse the output distribution over
generations, and reinforces whatever blind spots the transcripts contain. It
works only when there is a verifiable external signal to filter against, plus
deduplication and distribution checks. Without a ground-truth filter, a
self-generated corpus is an echo chamber with extra steps.

## Licences are a hard constraint, not a detail

Financial datasets and paper corpora carry terms that frequently forbid model
training outright, restrict it to research use, or forbid redistribution of
derived weights. "Free to download" and "trainable" are different questions.
Check the licence of every corpus before planning a training run on it, and
prefer corpora with an explicit permissive licence for both research and
derived-artifact use.

For market data specifically, note that broker and vendor feeds are usually
licensed for a specific use and often prohibit redistribution or automated
extraction beyond personal analysis. Establish what the intended use is before
choosing a source.