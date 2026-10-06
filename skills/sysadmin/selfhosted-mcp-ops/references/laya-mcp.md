# laya-mcp — service ops notes

## Unit wiring
- systemd user unit `laya-mcp.service`, venv `~/Work/laya-mcp/.venv` (mcp pinned `<2`).
- Drop-in sets: `LAYA_DEVICE=cpu`, `LAYA_PRELOAD=1`, `LAYA_MAX_LOADED=3`,
  `LAYA_MCP_TOKEN=<bearer>`, and **`LAYA_ENGLISH_MODEL=~/Work/laya-mcp/train/ckpt/laya-kurama-v3`**.
- Memory budget: peak RSS ≈ sum of the 3 preloaded checkpoints (~1.16B params total,
  ~9 GB observed) is BY DESIGN (`preload=1, max_loaded=3`), not a leak. Idle threads
  at 0.0% CPU + swap-resident pages = stale-page pressure; a service restart clears
  it and is cheaper than any tuning.

## The pinned checkpoint is live runtime data
`train/ckpt/laya-kurama-v3` looks like a training artifact (sits under `train/` next
to venvs and datasets) but the SERVER loads it on every boot. Never delete it during
disk reclaim. Before any purge under `~/Work/laya-mcp`, grep
`systemctl --user cat laya-mcp.service` for `Environment=` paths.

## Retrain recipe (checkpoint lost or needs refresh)
1. Rebuild the training venv (rebuildable, ~30 s):
   `bash ~/Work/laya-mcp/train/scripts/setup_env.sh`
   → torch cu130 + transformers + laya, isolated in `train/venvs/nn`.
2. The base english checkpoint lives in the HF cache at
   `/mnt/work/cache/huggingface` (NOT `~/.cache/huggingface` — the home copy is a
   symlink to it). Run with it visible:
   `cd ~/Work/laya-mcp/train && HF_HOME=/mnt/work/cache/huggingface \
   nohup venvs/nn/bin/python scripts/03c_finetune_r3.py > reports/v3_retrain.log 2>&1 &`
3. ~5 min total (2 epochs, GPU). Success line: `saved -> .../train/ckpt/laya-kurama-v3`.
   Log tail shows per-epoch train/val loss+acc (val_acc ≈ 0.98 is the historical norm).
4. `systemctl --user restart laya-mcp.service`, wait ~2 min for preload, then verify
   end-to-end via `POST /v1/systemone` with the bearer token:
   - `sudo rm -rf` style action → destructive noul ≈ 0.99
   - `ls -la` style action → destructive noul = 0.0
   Both must hold before calling the service healthy.

## Verification probes
- `GET /health` (with bearer) → `{status: ok, router_loaded: true}`.
- MCP: any harness `tools/list` ping; raw wire: `POST /v1/systemone` (state+questions).
- Latency log line format: `predict ms=<x> model=<name>` in the user journal —
  grep it for per-call timing history when auditing.
