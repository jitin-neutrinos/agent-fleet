#!/usr/bin/env bash
# Reconcile df against du, attribute writes to processes and churning files.
# Unprivileged. Read-only. Never deletes anything.
#
# Usage: df-du-reconcile.sh [mount] [churn_window_minutes]
#   ./df-du-reconcile.sh /home 70
set -uo pipefail

TARGET="${1:-/home}"
WIN="${2:-70}"
MIN_WRITE=$((512 * 1024 * 1024))   # only report processes past 512 MiB written

echo "=== 1. FILESYSTEM ==="
df -hT "$TARGET" | tail -1

echo
echo "=== 2. RECONCILIATION: df used vs du ==="
used=$(df --block-size=1 "$TARGET" | awk 'NR==2 {print $3}')
acc=0
for m in $(findmnt -rno TARGET,FSTYPE | awk -v t="$TARGET" '$2=="btrfs"{print $1}'); do
  s=$(du -xs --block-size=1 "$m" 2>/dev/null | awk '{print $1}')
  s=${s:-0}
  printf "  du %-10s %8.2f GiB\n" "$m" "$(awk -v b="$s" 'BEGIN{print b/1073741824}')"
  acc=$((acc + s))
done
printf "  %-14s %8.2f GiB\n" "du TOTAL" "$(awk -v b="$acc" 'BEGIN{print b/1073741824}')"
printf "  %-14s %8.2f GiB\n" "df USED" "$(awk -v b="$used" 'BEGIN{print b/1073741824}')"
printf "  %-14s %8.2f GiB   <-- invisible to du\n" "GAP" \
  "$(awk -v u="$used" -v a="$acc" 'BEGIN{print (u-a)/1073741824}')"
echo
echo "  On btrfs a gap above a few GB is almost always snapshots."
echo "  Next: sudo btrfs subvolume list / | grep <snapdir>   (see references/btrfs-snapshot-audit.md)"

echo
echo "=== 3. TOP WRITERS SINCE BOOT (/proc/<pid>/io write_bytes) ==="
for p in /proc/[0-9]*; do
  w=$(awk '/^write_bytes/{print $2}' "$p/io" 2>/dev/null)
  [ -n "${w:-}" ] || continue
  [ "$w" -gt "$MIN_WRITE" ] 2>/dev/null || continue
  exe=$(readlink "$p/exe" 2>/dev/null)
  exe=${exe##*/}
  cmd=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null | cut -c1-60)
  printf "  %8.2f GiB  %-20s %s\n" \
    "$(awk -v b="$w" 'BEGIN{print b/1073741824}')" "${exe:-?}" "$cmd"
done | sort -rn | head -20

echo
echo "=== 4. HOT FILES (largest, modified in last ${WIN} min) ==="
find "$TARGET" -xdev -type f -newermt "-${WIN} minutes" -printf '%s\t%p\n' 2>/dev/null \
  | sort -rn | head -15 \
  | awk -F'\t' '{printf "  %9.1f MiB  %s\n", $1/1048576, $2}'

echo
echo "=== 5. TOTAL CHURN IN WINDOW ==="
find "$TARGET" -xdev -type f -newermt "-${WIN} minutes" -printf '%s\n' 2>/dev/null \
  | awk -v w="$WIN" '{s+=$1} END {printf "  %.1f GiB modified in last %s minutes\n", s/1073741824, w}'

echo
echo "=== 6. LOAD (high load + churn together = a runaway loop) ==="
uptime