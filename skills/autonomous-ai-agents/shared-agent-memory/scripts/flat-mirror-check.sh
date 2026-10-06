#!/usr/bin/env bash
# flat-mirror-check.sh — conformance of a staged-FLAT skills mirror against the store.
# Flat staging collapses duplicate skill basenames keep-first, so a flat mirror's expected
# count = the store's count of DISTINCT basenames, not its raw SKILL.md count.
# Usage: bash flat-mirror-check.sh <store-skills-dir> <flat-mirror-dir>
set -eu
store=${1:?usage: flat-mirror-check.sh <store-skills-dir> <flat-mirror-dir>}
flat=${2:?usage: flat-mirror-check.sh <store-skills-dir> <flat-mirror-dir>}
names() { find "$1" -name SKILL.md -printf '%h\n' | xargs -r -n1 basename | sort; }
printf 'store SKILL.md (raw):      %s\n' "$(find "$store" -name SKILL.md | wc -l)"
printf 'store distinct basenames:  %s   <- expected flat-mirror count\n' "$(names "$store" | uniq | wc -l)"
printf 'flat mirror SKILL.md:      %s\n' "$(find "$flat" -name SKILL.md | wc -l)"
printf -- '--- in store, missing from flat ---\n'
comm -23 <(names "$store" | uniq) <(names "$flat" | uniq)
printf -- '--- in flat, not in store ---\n'
comm -13 <(names "$store" | uniq) <(names "$flat" | uniq)
