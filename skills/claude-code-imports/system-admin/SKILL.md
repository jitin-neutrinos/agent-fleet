---
name: system-admin
description: Linux system administration and monitoring
version: 1.0.0
author: terminal-skills
tags: [linux, system, monitoring, admin]
---

# Linux System Administration

## Overview
Core commands and best practices for Linux system administration, including system information viewing, resource monitoring, service management, etc.

## System Information

### Basic Information
```bash
# System version
cat /etc/os-release
uname -a

# Hostname
hostnamectl

# Uptime and load
uptime
```

### Hardware Information
```bash
# CPU information
lscpu
cat /proc/cpuinfo

# Memory information
free -h
cat /proc/meminfo

# Disk information
lsblk
df -h
```

## Resource Monitoring

### Real-time Monitoring
```bash
# Comprehensive monitoring
top
htop

# Memory monitoring
vmstat 1

# IO monitoring
iostat -x 1
iotop

# Network monitoring
iftop
nethogs
```

### Historical Data
```bash
# System activity report
sar -u 1 10    # CPU
sar -r 1 10    # Memory
sar -d 1 10    # Disk
```

## /home capacity guardrails (kurama-core, 2026-10-05)

`~/.local/bin/storage-guard.sh` runs every 6h via `storage-guard.timer`. Design rules, each
born from a real failure:

- **`/home` is btrfs at ~93% full; `/mnt/work` is a separate ext4 disk with 600 GB free.** When
  /home is tight the correct move is to relocate a cache or move cold data to /mnt/work — not to
  delete project files. `~/.cache/uv` (32 G) and `~/.cache/huggingface` (37 G) are the two
  biggest reclaimable items and neither is referenced by path.
- **NEVER auto-delete**: the NTFS disk under `/run/media/notjitin` (a standing deny rule in
  config.yaml — it blocks the agent even with `--yolo`), `/mnt/work`, `~/.cache/huggingface`
  model weights (chatterbox TTS + Qwen/Llama; all 87 blobs are referenced by 130 snapshot
  symlinks, zero orphans), or `Work/taal/target` (taal-server executes from `target/release`).
- **`uv cache prune` refuses** because ~36 `uv tool uvx` MCP servers are daemons holding the lock
  permanently. `--force` works and reclaimed 21 G. Never let a script give up on the lock and
  report success.
- **Report freed bytes from `shutil.disk_usage`, never from a `df` diff.** `df` prints whole
  gigabytes, which is how `machine-cleanup.sh` logged `freed 0 GB` on all three runs while uv grew
  11 G → 53 G.
- **The biggest single leak was a test harness**: `Work/taal/crates/taal-state/tests/integration.rs`
  copied the entire live `state.db` (~750 M) into `$TMPDIR` per run with no cleanup — 24 orphans,
  17 GB in three days. Fixed with an RAII `Drop` guard. Lesson: any test that copies a production
  DB needs a cleanup that runs on panic too.
- **`$TMPDIR` is `~/.hermes/cache/scratch`**, so "temp files" land in the Hermes scratch dir and
  the 24h sweeper will not catch a leak that keeps regenerating.
- **Check `lsof +L1` before concluding a deletion freed nothing.** Deleted-but-open files keep the
  space allocated until the holder exits.

## Service Management

### Systemd Services
```bash
# Service status
systemctl status service-name
systemctl is-active service-name

# Start/Stop services
systemctl start/stop/restart service-name

# Boot startup
systemctl enable/disable service-name

# View all services
systemctl list-units --type=service
```

## Common Scenarios

### Scenario 1: System Health Check
```bash
# Quick health check script
echo "=== System Load ===" && uptime
echo "=== Memory Usage ===" && free -h
echo "=== Disk Usage ===" && df -h
echo "=== Failed Services ===" && systemctl --failed
```

### Scenario 2: Troubleshoot High Load
```bash
# 1. Check load
uptime

# 2. Find high CPU processes
ps aux --sort=-%cpu | head -10

# 3. Find high memory processes
ps aux --sort=-%mem | head -10
```

## Troubleshooting

| Problem | Commands |
|---------|----------|
| System lag | `top`, `vmstat 1`, `iostat -x 1` |
| Disk full | `df -h`, `du -sh /*`, `ncdu` |
| Memory shortage | `free -h`, `ps aux --sort=-%mem` |
| Service abnormal | `systemctl status`, `journalctl -u` |
