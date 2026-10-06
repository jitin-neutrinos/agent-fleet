// SINGLE SOURCE OF TRUTH for every prompt surface that teaches an agent to emit Astra canvas cards.
// canvas-surface-sync.mjs renders this into: the harness rulebooks (CLAUDE.md, GEMINI.md, opencode
// AGENTS.md, ~/AGENTS.md), Hermes' SOUL.md, and the `## Canvas output` stanza in ~50 skills.
// Edit THIS file, run `node rules/canvas-surface-sync.mjs`, and every surface follows. `--check` exits 1 on drift.
//
// Facts here were verified 2026-10-04 against src/lib/canvas-schema.ts (BLOCK_TYPES + CHART_KINDS) and the
// reactive/media fixes in commits 9918edd + b158458. If the parser's type list changes, the generator FAILS
// until this table agrees — a silent count change is the drift class this file exists to kill.

export const EXPECTED_BLOCK_TYPES = 49;

export const CHART_KINDS = [
  "line", "area", "bar", "stack", "radial", "pie", "donut", "sankey", "treemap", "funnel", "scatter", "radar",
  // canvas v1 expansion: `box` is one series per group of raw samples (quartiles
  // + whisker computed by the renderer) and `histogram` bins one series of raw
  // samples into counts. Both take the ordinary {labels,series} shape.
  "box", "histogram", "errorbar", "candlestick", "waterfall", "violin"
];

// group order is the order surfaces list them in
export const GROUPS = [
  ["Data", ["kpi", "chart", "table", "heatmap"]],
  ["Structure", ["diagram", "graph", "tree", "gitgraph", "compare", "tabs", "accordion", "divider", "layout"]],
  ["Status", ["checklist", "steps", "progress", "timeline", "badges", "callout"]],
  ["Evidence", ["code", "terminal", "diff", "quote", "keyvalue", "references", "math", "theorem", "algorithm"]],
  ["Editable files", ["spreadsheet", "slides", "document", "text"]],
  ["Interactive", ["slider", "select", "multiselect", "segmented", "toggle", "search", "data"]],
  ["Media", ["image", "gallery", "video"]],
  ["Domain", ["palette", "scorecard", "compliance", "clause", "obligations", "schema", "sequence"]],
];

// shape = the JSON keys (? = optional). when = reach for it when… (<= 12 words)
export const TYPES = {
  kpi: { shape: "{label,value,delta?,trend?,spark?}", when: "a headline number, count or delta; spark:number[3..24] draws a trend line" },
  chart: { shape: "{chart,title?,scale?,refline?,p?,labels?,series:[{name,points?,error?,ohlc?}]}", when: "trends, distributions, flows; every chart needs a title and a unit" },
  table: { shape: "{columns,rows,stats?,colTypes?:(text|color|contrast|bar|delta|status)[],colMeta?,footnote?,sig?,units?}", when: "comparisons and findings; max 4 columns on a phone; `stats` makes the RENDERER compute the summary, never you" },
  heatmap: { shape: "{title?,rows,cols,values,cells?,thresholds?,scale?:sequential|diverging,center?}", when: "a matrix a table would force sideways scroll on (scores, activity by hour)" },
  diagram: { shape: "{layout:flow|relationship,direction?,nodes:[{id,label,detail?,kind?,note?}],edges:[{from,to,label?,note?}],summary?}", when: "how pieces connect; it grows, scrolls and zooms; add `summary` so a reader can follow it" },
  graph: { shape: "{title?,height?,nodes:[{id,label,kind?,weight?,detail?}],edges:[{source,target,kind?,label?,weight?}]}", when: "a relationship map or topology with many entities" },
  tree: { shape: "{nodes:[{id,label,detail?,children?,size?,lines?,kind?}],sort?,defaultDepth?,pruned?}", when: "file trees and hierarchies" },
  theorem: { shape: "{kind:lemma|proposition|corollary|theorem|proof,statement,proof?,refs?,number?}", when: "a mathematical or logical claim" },
  algorithm: { shape: "{steps:[{text,indent?,complexity?}],number?}", when: "a step-by-step procedure" },
  palette: { shape: "{title?,against?,colors:[{name?,value,role?,note?}],scale?,space?,type?,radius?,shadow?}", when: "design tokens: swatch grid with WCAG+APCA verdicts the RENDERER computes" },
  scorecard: { shape: "{title?,method:heuristic|sus|rice|custom,max?,items:[{criterion,score?,severity?,note?,evidence?}],verdict?}", when: "rubric rows; the renderer computes SUS/RICE arithmetic — send raw scores" },
  compliance: { shape: "{regime,asOf?,source?,items:[{ref,provision,obligation,due?,status,severity?,owner?,evidence?,consequence?,penalty?}]}", when: "statutory or WCAG audits; status/severity are declared enums; stamp asOf" },
  clause: { shape: "{title?,items:[{ref,heading?,text,children?,status?,risk?,flags?,playbook?,note?,source?}]}", when: "clause tree addressed by legal ref (12.3(a)(ii)); risk dots, never hue" },
  obligations: { shape: "{title?,rows:[{ref?,obligation,party,trigger?,due?,recurrence?,severity?,status?,consequence?,owner?,evidence?}]}", when: "obligations register; due takes contractual expressions; soonest-due first" },
  schema: { shape: "{title?,tables:[{name,rows?,columns:[{name,type,key?:PK|FK|NN|UQ,ref?,note?}],indexes?,note?}]}", when: "database schema; PK/FK/NN badges, FK ref navigable" },
  sequence: { shape: "{title?,actors:[{id,label,kind?}],messages:[{from,to,label?,kind?:sync|async|return|self,at?}]}", when: "ordered calls between lifelines; dangling ids drop the message, not the block" },
  gitgraph: { shape: "{title?,branches?:[{name,head?}],commits:[{id,branch?,message,parents?,author?,when?,tags?,merge?}]}", when: "branch history, forks and merges; commits newest first, a parent on another branch is a fork" },
  compare: { shape: "{items:[{name,caption?,badge?,points:[{text,tone}]}]}", when: "option A vs B, before vs after; tone is pro or con" },
  tabs: { shape: "{items:[{label,blocks}]}", when: "several views of ONE subject; one level deep only" },
  layout: { shape: "{layout:stack|bento|split|masonry|grid,cols?,blocks}", when: "blocks composed in one grid instead of a stack" },
  accordion: { shape: "{items:[{title,body?,blocks?,open?}]}", when: "detail the reader may skip: method, caveats, raw output" },
  divider: { shape: "{label?}", when: "a labelled break inside a long card" },
  checklist: { shape: "{items:[{text,status:done|open|fail}]}", when: "shipped vs not, audit results, what would have to be true" },
  steps: { shape: "{items:[{title,detail?,status:done|active|todo|fail}]}", when: "an ordered plan or phases; exactly one active" },
  progress: { shape: "{label,value,max?,unit?,status?,detail?}", when: "coverage, completion, budget used" },
  timeline: { shape: "{items:[{title,detail?,time?,status}]}", when: "what happened when; mark disproven hypotheses fail" },
  badges: { shape: "{items:[{label,tone}]}", when: "a one-line status or tag row at the top of a card" },
  callout: { shape: "{tone:info|warn|success|danger,title?,body}", when: "the one thing that must not be missed: the answer, the caveat, the gate" },
  code: { shape: "{language?,filename?,code}", when: "a command or snippet the reader may run" },
  math: { shape: "{tex,display?,label?}", when: "a formula, derivation or closed-form expression" },
  terminal: { shape: "{title?,command?,lines:[{text,tone}],exitCode?}", when: "a command with its real output as evidence" },
  diff: { shape: "{language?,filename?,hunks:[{header?,lines:[{op:add|del|ctx,text}]}]}", when: "a change worth reading line by line" },
  quote: { shape: "{text,attribution?,role?,context?}", when: "words worth their own surface: an expert, the user, a doc" },
  keyvalue: { shape: "{title?,items:[{key,value,mono?}]}", when: "exact facts: versions, paths and hashes (mono:true), config" },
  references: { shape: "{items:[{title,href?,note?}]}", when: "every claim's sources; real hrefs; say not opened if you did not open it" },
  spreadsheet: { shape: "{title?,filename?,sheets?,columns?,rows,header?}", when: "numbers the reader will change or take away as .xlsx" },
  slides: { shape: "{title?,filename?,slides:[{heading,bullets?,note?,layout?}]}", when: "a talk you are delivering, as .pptx" },
  document: { shape: "{title?,filename?,content:[{kind?,text}]}", when: "structured prose to edit or take away as .docx" },
  text: { shape: "{title?,filename?,content,language?}", when: "plain text or markdown to edit or take away" },
  slider: { shape: "{label,bind,min,max,step?,value?,unit?,format?}", when: "a number the reader should MOVE (what-if, sensitivity)" },
  select: { shape: "{label,bind,options:[{label,value}],value?}", when: "one choice from a list, driving other blocks" },
  multiselect: { shape: "{label,bind,options,value?:string[]}", when: "several choices at once, shown as chips" },
  segmented: { shape: "{label?,bind,options,value?}", when: "2 to 5 mutually exclusive views or scenarios" },
  toggle: { shape: "{label,bind,value?}", when: "show or hide something" },
  search: { shape: "{label?,bind,placeholder?}", when: "free-text filter over a `data` block" },
  data: { shape: "{name,columns?,rows,header?}", when: "the named dataset that bound tables and charts read; never drawn" },
  image: { shape: "{src,alt?,caption?}", when: "one image; src is a host path like ~/uploads/a.png or /home/…" },
  gallery: { shape: "{items:[{src,alt?,caption?}],layout?}", when: "2 to 12 images in a tap-to-zoom grid" },
  video: { shape: "{src,poster?,captions?,caption?}", when: "one clip; src is a host path, never base64" },
};

// The recipes: block ORDER is the rule. Each is verified to parse (research/R3 + the real parser).
export const RECIPES = [
  ["Research", "badges → callout → kpi ×3 → table → callout warn → references"],
  ["Data-viz", "kpi row → ONE chart → callout → accordion. What-ifs add state+slider and $expr kpis"],
  ["Brainstorm", "callout → heatmap or compare → checklist → segmented/select"],
  ["Status/report", "badges → progress ×N → table → checklist → callout danger. Failures in SAME card"],
  ["Hand-off", "callout warn → keyvalue → steps → callout danger → references"],
  ["Decision", "callout → compare → table → callout success"],
  ["Post-mortem", "callout danger → kpi ×3 → timeline → diagram lr → callout warn → table"],
  ["Session start", "A `[session-brief]` is injected: ONE greeting line, paste its card EXACTLY"],
  ["Legal report", "clause → obligations → compliance → references(cite) → callout risk"],
  ["Stats", "chart errorbar/refline + table sig colTypes → callout method"]
];

// Always-on rules for the harness block (kept short: cheap models read this)
export const HARNESS_RULES = [
  "Astra/Android: answer with canvas cards, not md tables. Prose argues; canvas evidences.",
  "Use blocks for data/structure. 2-4 cards/answer normal; don't split ONE idea across blocks. Use `page:a4` or `slide`.",
  "CLI: use prose. A `code` block containing ``` needs 4-backtick fence.",
  "Hex colors as WHOLE table cell/keyvalue render as swatches. Separate code/text into columns."
];

// Extra rules only the Hermes system prompt (SOUL.md) carries
export const SOUL_RULES = [
  "**Canvas is the default output on Astra, not an embellishment.** Reach for a card first, every time. Never bury structured data in prose when a block fits.",
  "Use it aggressively: several distinct cards per answer is correct. The anti-slop rule is about not fragmenting ONE idea across blocks, never about using too few cards.",
  "**Reactive**: when the answer is WHAT-IF, add top-level `\"state\":{…}` plus controls. `kpi.value` and `progress.value` accept `{\"$expr\":\"money(seats*price)\"}`; a `table` or `chart` reads a `data` block through `\"bind\":{\"$from\":\"name\",\"filter\":[…],\"sort\":{…},\"top\":8}`; chart series take `points:{\"$expr\":…}` and `visible:{\"$expr\":…}`; any block takes `visible:{\"$expr\":…}`. Helpers: min max round abs clamp sum avg len at range compound money pct compact fmt. Identifiers are only your `state` keys; a bad expression shows `—`, it never breaks the card.",
  "**Media**: `image`, `gallery` and `video` take host paths (`~/uploads/a.png`, `/home/…/clip.mp4`). Never base64, never `MEDIA:` tags inside a card.",
  "**Page format**: declare `\"page\":\"a4\"` for a long report and `\"page\":\"slide\"` for a deck; omit it for a short card. The card renders inside a real A4 or 16:9 page box, so the on-screen card IS the export — no separate export step, and no divergence between what you wrote and what downloads. One card is one page format, so a portrait/landscape instruction is a mistake: pick the format that matches the content, not the other axis.",
  "**Session start**: when a `[session-brief …]` block appears, it was built from the real memory stores. Greet in one line, paste its card unchanged, ask what to work on. Do not summarise, extend or invent memory.",
  "**Progress and status**: any report on work in progress, a phase boundary or a build/test result is a card (kpi row, steps/timeline, progress, checklist, one callout). State failures and deferrals in the same card as successes; never a card that reads all-green while something is broken. One progress card per report.",
  "**Gates**: reviews, approvals, reports, fix gates and clarifying questions render through the same blocks; build their bodies from them so an approval surface is reviewable at a glance.",
  "A canvas stays in the chat; only an approval or review gate notifies the phone. Do not promise a phone notification for a card.",
  "When unsure a card parses, validate it: `node ~/.hermes/skills/autonomous-ai-agents/structured-surface-emission/scripts/validate-canvas-spec.mjs <file>`. A repair that invents a block is worse than raw JSON shown honestly.",
  "**Swatches**: a colour code as a WHOLE `table` cell or `keyvalue` value (`#020C1B`, `rgb(…)`, `oklch(…)`) renders as a swatch of that colour plus the code. Palette and design-token reports are therefore plain tables of code values — no special block, no emoji fakery, no colour codes buried in prose. Mixed text in the cell suppresses the paint (whole-string match only), so name and code go in separate columns.",
];

// One stanza per kind of work; applied under `## Canvas output` to the skills listed in SKILL_GROUPS
export const STANZAS = {
  research: "Ship research as cards, not paragraphs: a `badges` row for depth and confidence, a `callout` with the answer first, `kpi` for headline counts, a `table` of claims with an evidence and confidence column, a warn `callout` for what would change the answer, and `references` with real hrefs for every claim.",
  reporting: "A report is a card with `\"page\":\"a4\"`, so it renders as the page it exports as: `badges` for state, `kpi` for what changed, `steps` or `timeline` with done/active/todo/fail, `progress` for coverage or budget, `checklist` for shipped vs deferred, one `callout` for what needs attention. Failures sit in the same card as successes.",
  "data-viz": "Put the numbers in a `data` block and bind a `chart` or `table` to it; never repeat a series in prose. `bar` compares categories, `line` shows time, `donut` only for under six shares, `heatmap` for two dimensions, `scatter` for correlation. Title every chart with its unit. Add `segmented` or `select` when the reader should pivot.",
  brainstorm: "Explore in cards the reader can weigh: a `callout` for the constraint first, `compare` for the top options with pro/con points, `heatmap` to score many ideas, `tree` for structure, `diagram` for flow. End with a `checklist` of open decisions and a `segmented` control for the choice you need.",
  "hand-off": "A hand-off is a surface: a warn `callout` with the next action first, `keyvalue` for exact state (mono paths and hashes), `steps` with exactly one active, a danger `callout` for gotchas, `references` for the files to read. Hand over artifacts and decisions, not the whole workspace.",
  review: "A review is a card: `kpi` severity counts, a `table` of findings (severity, file:line, one-line why), a danger `callout` for anything blocking, a `checklist` of fixes in order, and a `diff` when the fix is short enough to read.",
  planning: "Plan in editable cards: a `spreadsheet` for the task table the reader will adjust, a `document` for the spec, `steps` for the sequence, `progress` for budget, `timeline` for milestones, and a warn `callout` naming the riskiest assumption.",
};

// skill name -> stanza kind. Names are the SKILL.md frontmatter `name`.
export const SKILL_GROUPS = {
  research: ["grounded-citations", "competitor-news-monitor", "arxiv", "llm-wiki", "rss-feeds", "vendor-doc-mcp-research", "xurl", "reddit-reading", "youtube-content", "email-inbox-triage"],
  reporting: ["weekly-review-planning", "nobara-health-audit", "eagle3-review-logs", "hermes-web-ui-qa", "doc-maintenance", "documentation-writer", "ponytail-gain"],
  "data-viz": ["kpi-dashboard-design", "Pandas Data Analysis", "matplotlib", "seaborn", "duckdb", "exploratory-data-analysis", "data-storytelling", "querying-mlflow-metrics"],
  brainstorm: ["brainstorming", "baoyu-infographic", "architecture-diagram", "claude-design", "design-md", "impeccable", "supanova-premium-aesthetic", "manim-video"],
  "hand-off": ["agent-session-visibility", "shared-agent-memory", "delegated-build-agents", "subagent-driven-development", "finishing-a-development-branch", "executing-plans", "hermes-agent", "agentive-pipeline"],
  review: ["critical-code-reviewer", "code-review", "ponytail-review", "ponytail-audit", "security-auditor", "threat-modeling-expert", "review-skill", "code-review-playbook"],
  planning: ["writing-plans", "verification-before-completion", "fix-agent-issue", "diagnosing-bugs", "systematic-debugging", "algorithmic-trading-systems", "live-ops-dashboard"],
};
