# Serving stack after the campaign — retrieval wins, embedder swaps, deployment traps

## Measured retrieval matrix (neutrinos-mcp, sealed 1,698-question eval; dev 383 / test-gate 515)

| Config | dev r@10 | test-gate r@10 | dev MRR |
|---|---|---|---|
| bge-small dense | 76.8% | 71.7% | 0.440 |
| + hybrid RRF (BM25+dense, k=60) | 86.2% | 82.9% | 0.516 |
| + contextual chunk text | 88.3% | 84.1% | 0.543 |
| EmbeddingGemma-300M + contextual hybrid (FINAL) | 88.8% | 85.4% | 0.571 |
| fine-tuned bge-small (ablation) | 68.7% | 63.7% | — |

Rules:
- Hybrid RRF is the single biggest lever (+9pp over dense); BM25 alone can beat
  dense on identifier-heavy docs (error codes, property names, slugs).
- Contextual chunk text is free: embed `context_prefix | heading_path\n + text`,
  not bare text. The columns usually already exist in the DB.
- Retire the cross-encoder reranker when the embedder gets strong enough: rerank
  stopped adding recall/MRR after the Gemma swap while costing ~410ms/query.
- Fine-tuning the embedder degraded recall ~8pp despite falling training loss
  (matches arXiv:2505.19274). Any future fine-tuning proposal cites the ablation
  first; a falling loss is not a retrieval improvement.
- Embedder swaps: MTEB deltas CAN transfer to a domain corpus, but only the
  sealed-eval bake-off proves it. Swap = re-encode corpus + re-run the full eval.
  An open mirror may exist when the canonical repo is gated
  (unsloth/embeddinggemma-300m for google/embeddinggemma-300m).

## Embedding backend split (local GPU vs CI runner CPU)
- Local: torch + sentence-transformers venv; doc/query prompt strings per the
  model card ('title: none | text: ' / 'task: search result | query: ' for
  Gemma), normalize_embeddings=True, fp16. ~9.5k chunks = ~2 min on a 4070-class GPU.
- CI runner (GitHub Actions): fastembed ONNX only (no torch). fastembed supports
  Gemma-300m natively incl. a Q4 build. CPU full-corpus encode is HOURS-class —
  size the workflow timeout from a live measured run, never an estimate.
- Make the backend switchable (env flag, fastembed default) and guard the torch
  import so fastembed-only environments never import torch.

## FastMCP serving server + Docker packaging
- One server file serves stdio (local clients) and streamable HTTP
  (`server.py http`, port 8000) — same tools both ways.
- Bake model + data into the image at build (no runtime downloads); ship
  embeddings as fp16 npz (ids + (N,768), L2-normalized rows) + sqlite with an
  FTS5 table (content='chunk', content_rowid='id', rebuilt via
  `INSERT INTO <fts>(<fts>) VALUES('rebuild')`).
- HEALTHCHECK must perform a full MCP `initialize` POST to /mcp. A bare GET
  returns 400, and a `ping` without a session also returns 400 — both read as
  permanently unhealthy. Use a python urllib one-liner; confirm `docker ps`
  shows 'healthy' before calling it done.
- Warm query ~100ms; first query after start ~10s (model load). Size client
  timeouts for the cold case.
- Chunk ids must be derived EXACTLY as the legacy ingest did (same tokenizer /
  token_count derivation) or a rebuilt index mismatches the shipped one — a
  naive re-chunk reproduced only ~94% of chunk ids.

## Wiring into Hermes
- `echo Y | hermes mcp add <name> --command <venv-python> --args <server.py>` —
  the add is interactive ("Enable all N tools?") and cancels without the piped Y.
- Verify: `hermes mcp test <name>` (lists discovered tools).
- Sessions load MCPs at STARTUP only: a session that predates the registration
  keeps the old toolset until restarted. Tell the user to restart the session.

## Hosting (post-July-2026 HF policy change)
- HF Spaces: Docker/Gradio SDK requires PRO ($9/mo); free accounts get Static
  Spaces only (files, no server = no MCP) plus up to 2 ZeroGPU Gradio demos
  (time-sliced GPU, not a persistent server). Free create_repo(space_sdk=
  'docker') fails with 402 Payment Required — verify current policy before
  recommending HF free hosting.
- Free container hosts: Northflank Developer plan (1GB RAM, no cold starts) is
  the strongest remaining; Koyeb free (512MB) only fits a torch-free fastembed
  image; Render free sleeps at 15 min; Fly and Railway have no free tier.
- Always-available fallback: the home server's always-on container + a free
  Cloudflare Tunnel for a public HTTPS URL — implemented as a named tunnel with a
  permanent hostname (procedure in the Named Cloudflare Tunnel section above).
- Secrets: tokens go in .env (chmod 600) + .gitignore inside the package; prefer
  narrowly-scoped fine-grained tokens over full-access ones.

## Named Cloudflare Tunnel — the permanent-URL deployment
- Quick tunnels (`cloudflared tunnel --url http://localhost:8000`) mint a RANDOM
  trycloudflare.com subdomain per run: any restart/reboot reshuffles the URL and
  breaks every configured client. No workaround pins it — go straight to a named
  tunnel for anything real.
- Procedure: (1) install cloudflared (dnf has no package — install the GitHub
  release binary to /usr/local/bin); (2) `cloudflared tunnel login` (browser
  auth, writes ~/.cloudflared/cert.pem); (3) `cloudflared tunnel create <name>`
  (writes <uuid>.json credentials); (4) `cloudflared tunnel route dns <name>
  mcp.<domain>` — requires the domain's nameservers already on Cloudflare
  (DuckDNS-style free subdomains do NOT work); (5) write ~/.cloudflared/config.yml
  (tunnel id, credentials-file, ingress: hostname→http://localhost:8000, fallback
  http_status:404); (6) systemd user service running `cloudflared tunnel --
  no-autoupdate run <name>`, Restart=always.
- The tunnel is outbound-only: no router ports open, works behind CGNAT, the
  static IP stays unused. Moving hostnames later is attach/detach — the tunnel
  UUID is permanent; adding `mcp.<other-domain>` is one ingress rule + one CNAME.
- Ingress path-routing on the same hostname serves multiple apps: put a `path:`
  regex rule BEFORE the catch-all service rule (first match wins), e.g.
  `path: ^/install(\.sh|\.py|-<name>\.py)?$` → static file server, then the
  hostname rule → the MCP. Use this to host a public install one-liner
  (`curl -fsSL https://mcp.<domain>/install.sh | bash`) alongside the /mcp
  endpoint on one hostname; a static file server (python3 http.server) as a
  systemd user unit serves the script from disk — updates need only a file
  copy, no service restart.
- Verify with a full MCP handshake (initialize → tools/list → tools/call) through
  the public URL; warm latency through the edge was ~42-50ms. A curl POST can
  succeed while python-urllib gets a 403 — Cloudflare bot-scoring on the default
  python UA; send a real User-Agent header before debugging the tunnel.
- Endpoint is public/unauthenticated by default. Before wide exposure add a
  Cloudflare Access service token (free, ~10 min).
- Streamable-HTTP MCPs work fine through the tunnel (POST responses stream);
  the known quick-tunnel SSE GET-buffering bug and the 200-request cap
  do not affect this stack.

## Registering the remote MCP across harnesses
- Claude Code: `claude mcp add --transport http <name> <url>`; `claude mcp list`
  to verify; removals via `claude mcp remove <name>`.
- agy: `agy mcp add <name> <url>` — http/https URLs auto-detect as type http
  (config lands in ~/.gemini/config/mcp_config.json). Also sweep
  ~/.gemini/antigravity-cli/mcp/ for stale per-server install dirs.
- opencode: `opencode mcp add <name> --url <url>` (writes "type": "remote" into
  ~/.config/opencode/opencode.json).
- Hermes: edit ~/.hermes/config.yaml `mcp_servers:` directly ({name: {url: ...}}) —
  `hermes mcp add <name> --url <url>` prompts via /dev/tty and cancels in
  non-tty even with `echo Y |`. When key-matching the config, pick the mcp key
  that is NON-EMPTY: a stale empty `mcpServers:` sibling of the real
  `mcp_servers:` key makes naive first-dict-match write into a config hermes
  never reads. Then `hermes mcp test <name>` to verify (connect + tool list).
- A ready-made detector/installer covering all harnesses (including Codex,
  Gemini CLI, Cursor, VS Code forks, generic ~/.mcp.json) ships as
  `scripts/install-mcp-everywhere.sh` in this skill — run it instead of
  hand-typing per-harness commands; supports --remove and is idempotent.
- `scripts/install-neutrinos-docs-mcp.py` is the public-facing variant: same
  detection but with a branded TUI (pixel-art logo, single Neutrinos-Blue
  accent — brand rules forbid a second accent color; status glyphs ✓/•/✗ key
  on exact status strings like "MCP added", so when editing keep the renderer
  and the status strings in sync). Serve it over the tunnel with the
  path-routing ingress in the Named Cloudflare Tunnel section and the
  `curl -fsSL <url>/install.sh | bash` one-liner becomes the user-facing
  install command.
- When replacing old registrations, sweep EVERY harness for duplicate/stale
  entries pointing at the old server (the same binary is often registered under
  multiple names — check what a name actually serves before deleting a similarly
  named entry; different-product MCPs share prefixes).

## ONNX serving swap (2026-10-02, shipped) + laya reranker (killed)
- Torch-free serving works and is proven: export the ST chain (backbone →
  masked mean-pool → Dense → Dense → L2) as ONE onnx graph; parity gate
  worst-cosine ≥0.999 vs `SentenceTransformer.encode` on 100 sealed dev
  questions. Result: 2× faster CPU queries (45→22 ms), warm RSS −660 MB,
  zero torch maps in the serving process. Scripts live in neutrinos-mcp
  `mcp-server/{export_onnx_embedder,onnx_embedder,quantize_embedder}.py`.
- transformers-5 Gemma3 → ONNX gotcha: TorchScript export dies with
  `RuntimeError: unordered_map::at` in the mask factory;
  `attn_implementation="eager"` does NOT fix it. Feed PREBUILT 4D additive
  masks as traced inputs — `Gemma3TextModel.forward` accepts
  `attention_mask={"full_attention": 4D, "sliding_attention": 4D}`. Mask
  semantics for embeddinggemma-300m (bidirectional, sliding_window=512):
  full = padding-only; sliding = causal OR |q−k|<512, both AND padding.
- Load `tokenizer.json` directly via `tokenizers.Tokenizer.from_file` —
  importing `transformers.AutoTokenizer` drags torch into the process and
  defeats the whole swap (check `/proc/<pid>/maps | grep -c torch`).
- int8 dynamic quantization measured NEGATIVE on this model: worst cosine
  0.976 (<0.999 gate) and batch latency regression. Re-run the gate before
  ever adopting; don't assume.
- Laya (ModernBERT choice-head) as docs reranker: KILLED on sealed eval.
  Fine-tuned (LoRA r16/α32 + head, 508 sealed questions, 5–10 options with
  160-char chunk prefixes) → dev acc@1 peaked 0.274 (chance 0.2), always
  best at epoch 1 then overfit; full-stack hybrid+laya = r@5 .611 vs
  hybrid .812 (−20pp). Structural: option prefixes (48-token cap in
  build_sequence) can't separate version-sibling doc chunks. Second
  reranker failure after bge-reranker — for THIS corpus, hybrid RRF + a
  strong embedder is the ceiling; do not reopen without a fundamentally
  richer option representation (e.g. full-chunk cross-encoder).
- install.sh wrapper staleness trap: the one-liner wrapper at
  ~/scratch/mcp-install-www/install.sh kept pointing at the dead
  mcp.glitchzerolabs.com domain after the endpoint moved to
  neutrinos-mcp.jitinnair.com — anyone running the documented command got a
  530. When a public endpoint moves, sweep every artifact that embeds the
  old URL (wrapper scripts, docs, TUI text), not just the main config.

## Oct-2 optimization sweep (p99 push) — three levers tested, stack is FINAL
- Weighted-fusion grid (49 configs: weighted RRF a×κ×N + CC min-max, tuned
  on dev, verified on test-gate): dev gains (+3.1pp r@5) DID NOT transfer —
  best (cc_a0.6_N50) on test-gate = MRR +1.6pp, r@5 −0.4pp. Matches
  arXiv:2210.11934 (tuned fusion generalizes poorly out-of-domain). Parked:
  not worth prod complexity; equal RRF k=60 stands.
- Qwen3-Embedding-0.6B bake-off (MTEB-Eng ~71.7 claim vs Gemma 69.7):
  KILLED 0/3 metrics on test-gate (r@5 .765 vs .808, r@10 .854 vs .882,
  MRR .536 vs .598). Second leaderboard-transfer failure on this corpus
  (first was fine-tuned bge-small, −8pp). Lesson now doubly proven:
  benchmark deltas are hypotheses; only the sealed bake-off decides.
  Cache kept: rerank/qwen3_corpus_emb.npz; script eval_qwen3_bakeoff.py.
- FINAL-HOLDOUT READ (single, 2026-10-02; 292 questions never used in any
  tuning) — the certified confidence numbers for the production stack:
  hybrid recall@5=.8253 recall@10=.8904 MRR=.6179 (dense .8151/.8801/.5807;
  laya rerank confirms its kill on holdout too: .6610/.4362). THIS POOL IS
  NOW SPENT — any future model change must tune on train/dev, confirm on
  test-gate, and a NEW holdout must be generated from post-Sep corpus
  growth before the next "final" claim.
- GPU protocol for shared-card runs: docker stop content-comfyui frees
  ~4.3 GiB (4070 Ti SUPER 16GB); restore with docker start; the stack's
  evals batch fine alongside at batch 12.
- Laya choice questions: criteria dict KEYS are the options — duplicate
  keys silently collapse and corrupt labels; assert unique prefixes.
- Frozen-corpus eval pattern: encode corpus once on CUDA
  (encode_frozen_corpus.py → npz cache), embed queries live with the ONNX
  serving artifact; never re-encode 7.7K docs on CPU (hours-class).
- GPU shared with ComfyUI (`content-comfyui` container, ~4.3 GiB): batch 12
  fits alongside; bigger jobs ask/stop it; restore `docker start
  content-comfyui`.

## GitHub Actions as the ingest/publish pipeline
- The lastmod-diff scraper is catch-up-native: missed/delayed cron runs lose
  nothing — the next success diffs against the last committed state. This makes
  Actions-cron unreliability (UTC-only, 5-30min drift, occasional skipped runs)
  self-healing.
- Guard the known trap: scheduled workflows auto-DISABLE after 60 days of repo
  inactivity (successful runs do not count as activity). Fix: commit state on
  change days + a monthly keepalive commit + a dead-man's-switch ping
  (healthchecks.io) alerted on absence of a success ping in >1 interval.
- Set `concurrency: group: ingest, cancel-in-progress: false` so overlapping
  runs queue instead of racing.
- Validation gates must pass BEFORE pushing artifacts to the serving target:
  minimum chunk/topic counts, BM25 smoke queries, npz shape/norm checks,
  sampled id existence in both index and DB.
- Full pipeline + selftest: `mcp-server/ingest_pipeline.py` (env-flag backend:
  fastembed default for CI, `INGEST_EMBED_BACKEND=st` GPU path locally) with
  gates in `mcp-server/validate_index.py` — minimum chunk/topic counts, BM25
  smoke queries, npz shape/norm checks, sampled id existence in both artifacts.
  The selftest reproduces the shipped index within cosine >= 0.9998 of the
  serving embeddings; run it after ANY change to chunk derivation.
- Files >10MB on HF repos need Git-LFS (a 30-45MB DB+npz pair qualifies).
- Delegation fallback chain that actually held: primary CLI harness can fail
  with opaque 'Unexpected server error' while its provider API answers curl 200
  (integration fault, not quota) — probe the API directly to distinguish, then
  fall through the user's standing chain (GLM harness -> agy -> direct API ->
  subagent). Route around, don't debug the harness mid-task.
