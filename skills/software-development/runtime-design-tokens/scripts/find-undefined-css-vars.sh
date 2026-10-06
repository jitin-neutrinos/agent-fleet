#!/usr/bin/env bash
# find-undefined-css-vars.sh — report custom properties a stylesheet READS but never DEFINES.
#
#   ./find-undefined-css-vars.sh [stylesheet]     (default: src/index.css)
#
# Why this exists: an undefined var() is invalid-at-computed-value, so the whole
# declaration is dropped and the property silently falls back to its INITIAL value.
# A border-radius phantom renders 0px (square) — plausible enough to survive review.
# A color phantom renders transparent. A spacing phantom collapses layout. Nothing is
# logged anywhere, so set difference is the only reliable detector.
set -euo pipefail

CSS="${1:-src/index.css}"
[ -f "$CSS" ] || { echo "no such file: $CSS" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# every var(--x) reference, token name only
grep -oE 'var\(\s*--[a-zA-Z0-9_-]+' "$CSS" | sed -E 's/var\(\s*//' | sort -u > "$TMP/used"

# every custom property definition (leading position or after a ; { or whitespace)
grep -oE '(^|[;{[:space:]])--[a-zA-Z0-9_-]+[[:space:]]*:' "$CSS" \
  | grep -oE '\-\-[a-zA-Z0-9_-]+' | sort -u > "$TMP/defined"

PHANTOMS="$(comm -23 "$TMP/used" "$TMP/defined")"
printf 'stylesheet: %s\n' "$CSS"
printf 'referenced: %s   defined: %s\n' "$(wc -l < "$TMP/used")" "$(wc -l < "$TMP/defined")"

if [ -z "$PHANTOMS" ]; then
  echo 'OK — every custom property referenced here is also defined here.'
  echo 'NOTE: a token may be defined in ANOTHER stylesheet or injected at runtime by a'
  echo '      theme engine. This check is single-file by design; grep the whole tree and'
  echo '      a built bundle before declaring a token phantom.'
  exit 0
fi

echo
echo 'PHANTOM TOKENS (referenced, never defined in this file):'
echo "$PHANTOMS" | sed 's/^/  /'
echo
echo 'Each renders at its INITIAL value:'
echo '  border-radius / margin / padding / width  ->  0px / auto'
echo '  color / background-color                  ->  transparent'
echo '  calc(var(--phantom) - Npx)               ->  also invalid, also 0px'
exit 1
