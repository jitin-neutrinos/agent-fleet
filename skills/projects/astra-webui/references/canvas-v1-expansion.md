# Canvas v1 expansion (2026-10-05) — verified lessons

Measured research (saved: repo scratch/canvas-research-20261005.json) rejected on bundle cost:
mermaid 5253 kB/1490 gz, plotly 4721 kB, mathjax 1580 kB, @observablehq/plot 385 kB (no violinY),
react-arborist 139 kB+dnd+redux, lightweight-charts 159 kB (canvas 2D fillStyle SILENTLY ignores
CSS vars; attribution clause in README), smiles-drawer, @dbml/core (21 MB), gitgraph libs (archived).еня

Integrated (commits 5777b4c ff10cb9 b2339af 8c07425 8d09c60): layout composite block (reuses
src/lib/bento.ts + .mg-* CSS, 0 kB); shiki@4.5 fine-grained (createHighlighterCore + JS regex engine
+ createCssVariablesTheme variablePrefix --code-, per-lang dynamic chunks, lazy); math block katex
(throwOnError:false; CSS import must be SIDE-EFFECT import — `import x from 'katex.min.css'` fails
rolldown build); diagram node.shape:'entity'+fields[]+edge.cardinality_symbols+'orthogonal';
tree sanitizer now carries detail/children (3rd fix of the sanitizer-drops-fields bug class).

HARD RULES that keep biting: every new block type needs a sanitizer case + schema case + tests —
a missing sanitizer case silently DROPS the block (shipped 3x: accordion, tabs, gitgraph).
Fleet sync: adding a block type REQUIRES bumping EXPECTED_BLOCK_TYPES + CHART_KINDS in
~/Work/infra/agent-fleet/rules/canvas-surface-data.mjs in the SAME commit (sync exits 2 on drift).
Bundle attribution: build the agent's patch on the true pre-work base in an isolated worktree —
building the shared dirty tree shows other sessions' uncommitted code in YOUR number.
Parser does not cap; sanitizer does (tree node cap 100 = sanitizer's alone).
