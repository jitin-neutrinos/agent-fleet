---
name: telegram-media-delivery
description: "Use when sending files to Telegram via MEDIA tags."
---

# Sending media to Telegram from containerized Hermes

## The pitfall

Docker terminal backend: the **host gateway** uploads attachments, not the container
(docs: hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
`MEDIA:/tmp/...` (container-only path) fails **silently** — user gets nothing.

Verified: `MEDIA:/tmp/avatar.png` → never delivered. Same file via `/workspace` → delivered.

## Procedure

1. Write the file to **`/workspace/<name>`** (rw bind of host `@home` subvolume — host-visible).
2. Emit bare, on its own line: `MEDIA:/workspace/myfile.jpg` (never in code fences).

## Does NOT work

- `MEDIA:/tmp/...`, `/root/...` — container overlay, silently dropped.
- `~/.hermes/cache/*`, `~/.hermes/images` — mounted **read-only**; `cp` fails.

## Notes

- Images: png jpg jpeg gif webp bmp tiff svg · Video: mp4 mov webm mkv avi.
- If a png won't land, re-encode JPEG q92. Clean up one-off files from /workspace after.
