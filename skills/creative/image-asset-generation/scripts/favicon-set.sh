#!/usr/bin/env bash
# favicon-set.sh — master PNG -> web favicon set + QA preview.
# Usage: bash favicon-set.sh <master.png> <out-dir>
# Produces 16/32/48/180/192/512 px PNGs, favicon.ico, and preview-32.png
# (32px upscaled 9x with hard pixels — feed it to vision_analyze to judge
# small-size legibility of the mark).
set -euo pipefail
MASTER="${1:?usage: favicon-set.sh <master.png> <out-dir>}"
OUT="${2:?usage: favicon-set.sh <master.png> <out-dir>}"
mkdir -p "$OUT"

magick "$MASTER" -resize 512x512 "$OUT/favicon-512.png"
magick "$MASTER" -resize 192x192 "$OUT/favicon-192.png"
magick "$MASTER" -resize 180x180 "$OUT/favicon-180.png"
magick "$MASTER" -resize 48x48 -unsharp 0x1 "$OUT/favicon-48.png"
magick "$MASTER" -resize 32x32 -unsharp 0x1 "$OUT/favicon-32.png"
magick "$MASTER" -resize 16x16 -unsharp 0x1 "$OUT/favicon-16.png"
magick "$OUT/favicon-16.png" "$OUT/favicon-32.png" "$OUT/favicon-48.png" "$OUT/favicon.ico"
magick "$OUT/favicon-32.png" -filter point -resize 288x288 "$OUT/preview-32.png"

echo "wrote favicon set + preview-32.png to $OUT"
