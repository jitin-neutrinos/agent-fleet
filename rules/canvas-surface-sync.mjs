#!/usr/bin/env node
// rules/canvas-surface-sync.mjs — render canvas-surface-data.mjs into every prompt surface:
// the harness rulebooks (CLAUDE.md / GEMINI.md / opencode AGENTS.md / ~/AGENTS.md), Hermes' SOUL.md
// and the `## Canvas output` stanza in the skills named by SKILL_GROUPS.
//
//   node rules/canvas-surface-sync.mjs [--home <dir>] [--schema <path>] [--check] [--json] [--no-backup]
//
// Marker-delimited and idempotent (same shape as rules/install-rulebooks.sh): replace between markers,
// else append. The parser (canvas-schema.ts) is the truth — if it and the data module disagree, fail
// before writing anything. `--check` never writes, never backs up, exits 1 on drift.
import fs from "node:fs";
import nodePath from "node:path";
import {
  EXPECTED_BLOCK_TYPES,
  CHART_KINDS,
  GROUPS,
  TYPES,
  RECIPES,
  HARNESS_RULES,
  SOUL_RULES,
  STANZAS,
  SKILL_GROUPS,
} from "./canvas-surface-data.mjs";

const MARKERS = {
  harness: ["<!-- astra-canvas:start -->", "<!-- astra-canvas:end -->"],
  soul: ["<!-- astra-canvas:soul:start -->", "<!-- astra-canvas:soul:end -->"],
  skill: ["<!-- canvas-output:start -->", "<!-- canvas-output:end -->"],
};
const HARNESS_TARGETS = [".claude/CLAUDE.md", ".gemini/GEMINI.md", ".config/opencode/AGENTS.md", "AGENTS.md"];
const SOUL_TARGET = ".hermes/SOUL.md";
const SKILLS_DIR = ".hermes/skills";
const BACKUPS_REL = ".hermes/backups/canvas-sync";
const MAX_HARNESS_BLOCK = 2400; // chars; ~450 tokens of rulebook budget
const BACKUP_KEEP = 20;

function fail(msg) {
  process.stderr.write(`canvas-surface-sync: ${msg}\n`);
  process.exit(2);
}

// ---------------------------------------------------------------- args
function parseArgs(argv) {
  const o = { home: process.env.HOME || "", schema: null, check: false, json: false, backup: true };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--check") o.check = true;
    else if (a === "--json") o.json = true;
    else if (a === "--no-backup") o.backup = false;
    else if (a === "--home" || a === "--schema") {
      const v = argv[++i];
      if (v === undefined) fail(`--${a.slice(2)} needs a value`);
      o[a.slice(2)] = v;
    } else fail(`unknown argument: ${a}`);
  }
  return o;
}

// ---------------------------------------------------------------- step A: the parser is the truth
function extractSet(src, name, schemaPath) {
  const m = new RegExp(`const\\s+${name}\\s*=\\s*new Set\\(\\s*\\[([\\s\\S]*?)\\]\\s*\\)`).exec(src);
  if (!m) fail(`parser truth missing in ${schemaPath}: const ${name} = new Set([ … ]);`);
  // Set literals here are bare quoted names; `//` never appears inside one, so strip comments first.
  const body = m[1].replace(/^\s*\/\/[^\n]*$/gm, "").replace(/\s\/\/[^\n]*/g, "");
  return [...body.matchAll(/"([^"]*)"/g)].map((x) => x[1]);
}

function readParserSets(schemaPath) {
  if (!fs.existsSync(schemaPath)) fail(`schema not found: ${schemaPath}`);
  const src = fs.readFileSync(schemaPath, "utf8");
  return {
    types: extractSet(src, "BLOCK_TYPES", schemaPath),
    charts: extractSet(src, "CHART_KINDS", schemaPath),
  };
}

function compareSets(label, mine, theirs) {
  const extra = mine.filter((x) => !theirs.includes(x));
  const missing = theirs.filter((x) => !mine.includes(x));
  return { label, extra, missing };
}

function verifyAgainstData(parser) {
  const problems = [
    compareSets("BLOCK_TYPES", Object.keys(TYPES), parser.types),
    compareSets("CHART_KINDS", CHART_KINDS, parser.charts),
  ];
  if (parser.types.length !== EXPECTED_BLOCK_TYPES) {
    problems.push({ label: "EXPECTED_BLOCK_TYPES", extra: [], missing: [`parser has ${parser.types.length}, data module expects ${EXPECTED_BLOCK_TYPES}`] });
  }
  const bad = problems.filter((p) => p.extra.length || p.missing.length);
  if (!bad.length) return;
  const out = ["canvas-surface-sync: parser mismatch — update rules/canvas-surface-data.mjs"];
  for (const p of bad) {
    out.push(`  ${p.label}:`);
    for (const x of p.missing) out.push(`    parser has it, the data module does not: ${x}`);
    for (const x of p.extra) out.push(`    data module has it, the parser does not: ${x}`);
  }
  fail(out.join("\n"));
}

// ---------------------------------------------------------------- step B: render
const esc = (s) => s.replace(/\|/g, "\\|");
const bt = (s) => "`" + s + "`";

// Parenthetical qualifiers carry the detail; the harness block has no room for them and the
// directive doc + SOUL.md keep the full recipes. Block ORDER and names stay intact.
const compressRecipe = (body) => body.replace(/\s*\([^()]*\)/g, "").replace(/\s{2,}/g, " ").trim();

function renderHarness(n) {
  const block = [
    MARKERS.harness[0],
    "## Astra canvas — answer with cards, not prose walls",
    "",
    ...HARNESS_RULES.map((r) => `- ${r}`),
    "",
    'Emit a fenced ```astra-canvas JSON block `{"v":1,"title":?,"state":?,"blocks":[…]}`. ' + n + " block types (closed set):",
    ...GROUPS.map(([g, types]) => `- **${g}:** ${types.map(bt).join(" ")}`),
    "",
    "Chart kinds: " + CHART_KINDS.map(bt).join(" ") + ".",
    "",
    "Recipes — block order is the rule:",
    ...RECIPES.map(([name, body]) => `- **${name}:** ${compressRecipe(body)}`),
    "",
    "Shapes, aliases and worked examples: `~/Work/projects/astra-webui/docs/canvas-directive.md`.",
    MARKERS.harness[1],
  ].join("\n");
  if (block.length > MAX_HARNESS_BLOCK) {
    fail(`harness block is ${block.length} chars, over the ${MAX_HARNESS_BLOCK} budget — shorten HARNESS_RULES/RECIPES`);
  }
  return block;
}

function renderSoul(n) {
  const rows = [];
  for (const [, types] of GROUPS) {
    for (const t of types) {
      const { shape, when } = TYPES[t];
      rows.push(`| ${bt(t)} | ${bt(esc(shape))} | ${esc(when)} |`);
    }
  }
  return [
    MARKERS.soul[0],
    "## Generative UI — the Astra canvas (standing mandate)",
    "",
    ...SOUL_RULES.flatMap((r) => [r, ""]),
    `### Block vocabulary (closed set, ${n} types)`,
    "",
    "| type | shape | reach for it when |",
    "|---|---|---|",
    ...rows, // one unbroken run: no prose between rows
    "",
    "Chart kinds: " + CHART_KINDS.map(bt).join(" ") + '. `chart:"graph"` is NOT a chart — `graph` is its own block.',
    "",
    "### Recipes — block order is the rule",
    "",
    ...RECIPES.map(([name, body]) => `- **${name}:** ${body}`),
    "",
    "Full schema, aliases and worked examples: `~/Work/projects/astra-webui/docs/canvas-directive.md`.",
    MARKERS.soul[1],
  ].join("\n");
}

const renderSkill = (stanza) => [MARKERS.skill[0], "## Canvas output", "", stanza, MARKERS.skill[1]].join("\n");

// ---------------------------------------------------------------- writes (marker-delimited, idempotent)
function replaceBetween(text, [start, end], block) {
  const i = text.indexOf(start);
  if (i < 0) return null;
  const j = text.indexOf(end, i + start.length);
  if (j < 0) return null;
  return text.slice(0, i) + block + text.slice(j + end.length);
}

// blank line, block, trailing newline — trailing blank lines on the file are trimmed away
function appendBlock(text, block) {
  const trimmed = text.replace(/\s+$/, "");
  return trimmed ? `${trimmed}\n\n${block}\n` : `${block}\n`;
}

// one-time migration: the old hand-written section ran from its heading to the next `## ` heading
function migrateSoul(text, block) {
  const H = "## Generative UI";
  const at = text.startsWith(H) ? 0 : text.indexOf(`\n${H}`);
  if (at < 0) return appendBlock(text, block);
  const start = text.startsWith(H) ? 0 : at + 1;
  const next = text.indexOf("\n## ", start + H.length);
  const end = next < 0 ? text.length : next + 1;
  return text.slice(0, start) + block + "\n" + text.slice(end);
}

function writeAtomic(file, text) {
  const tmp = nodePath.join(nodePath.dirname(file), `.${nodePath.basename(file)}.canvas-sync.tmp`);
  fs.writeFileSync(tmp, text);
  fs.renameSync(tmp, file);
}

// ---------------------------------------------------------------- step C: targets
function collectSkills(root) {
  const files = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = nodePath.join(dir, e.name);
      const isDir = e.isDirectory() || (e.isSymbolicLink() && fs.statSync(p).isDirectory());
      if (isDir) walk(p);
      else if (e.name === "SKILL.md") files.push(p);
    }
  };
  if (fs.existsSync(root)) walk(root);
  const skills = [];
  for (const p of files.sort()) {
    const line = fs.readFileSync(p, "utf8").split("\n", 15).find((l) => /^name:/.test(l));
    if (!line) continue;
    const name = line.slice("name:".length).trim().replace(/^["']|["']$/g, "").trim();
    if (name) skills.push({ path: p, name });
  }
  return skills;
}

function planTargets(home, harness, soul) {
  const targets = [];
  const add = (file, kind, extra) => targets.push({ path: file, kind, ...extra });

  for (const rel of HARNESS_TARGETS) {
    const file = nodePath.join(home, rel);
    if (!fs.existsSync(nodePath.dirname(file))) {
      add(file, "harness", { skip: "no parent directory" });
      continue;
    }
    if (!fs.existsSync(file)) {
      // ~/AGENTS.md is only ever appended to an existing file; the harness files may be created.
      if (rel === "AGENTS.md") add(file, "harness", { skip: "file missing" });
      else add(file, "harness", { original: null, desired: `${harness}\n` });
      continue;
    }
    const text = fs.readFileSync(file, "utf8");
    add(file, "harness", { original: text, desired: replaceBetween(text, MARKERS.harness, harness) ?? appendBlock(text, harness) });
  }

  const soulFile = nodePath.join(home, SOUL_TARGET);
  if (!fs.existsSync(nodePath.dirname(soulFile))) add(soulFile, "soul", { skip: "no parent directory" });
  else if (!fs.existsSync(soulFile)) add(soulFile, "soul", { skip: "file missing" });
  else {
    const text = fs.readFileSync(soulFile, "utf8");
    add(soulFile, "soul", { original: text, desired: replaceBetween(text, MARKERS.soul, soul) ?? migrateSoul(text, soul) });
  }

  const found = collectSkills(nodePath.join(home, SKILLS_DIR));
  const byName = new Map();
  for (const s of found) {
    if (!byName.has(s.name)) byName.set(s.name, []);
    byName.get(s.name).push(s.path);
  }
  const missingSkills = [];
  const ambiguousSkills = [];
  for (const [kind, names] of Object.entries(SKILL_GROUPS)) {
    for (const name of names) {
      const hits = byName.get(name) || [];
      if (!hits.length) {
        missingSkills.push(name);
        continue;
      }
      if (hits.length > 1) ambiguousSkills.push(name);
      const file = hits[0]; // first in sorted path order; the rest are reported, not written
      const text = fs.readFileSync(file, "utf8");
      const block = renderSkill(STANZAS[kind]);
      add(file, "skill", { skill: name, original: text, desired: replaceBetween(text, MARKERS.skill, block) ?? appendBlock(text, block) });
    }
  }
  return { targets, missingSkills, ambiguousSkills };
}

// ---------------------------------------------------------------- backups
function backup(home, changed, enabled) {
  if (!enabled || !changed.length) return;
  const root = nodePath.join(home, BACKUPS_REL);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15).replace("T", "-");
  let dir = stamp;
  for (let n = 1; fs.existsSync(nodePath.join(root, dir)); n++) dir = `${stamp}-${String(n).padStart(3, "0")}`;
  const run = nodePath.join(root, dir);
  fs.mkdirSync(run, { recursive: true });
  for (const t of changed) {
    const flat = nodePath.relative(home, t.path).split(nodePath.sep).join("__");
    fs.copyFileSync(t.path, nodePath.join(run, flat));
  }
  const runs = fs
    .readdirSync(root, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => ({ name: e.name, m: fs.statSync(nodePath.join(root, e.name)).mtimeMs }))
    .sort((a, b) => a.m - b.m || (a.name < b.name ? -1 : 1));
  for (const old of runs.slice(0, Math.max(0, runs.length - BACKUP_KEEP))) fs.rmSync(nodePath.join(root, old.name), { recursive: true });
}

// ---------------------------------------------------------------- main
function main() {
  const o = parseArgs(process.argv.slice(2));
  const home = nodePath.resolve(o.home);
  if (!fs.existsSync(home)) fail(`home not found: ${home}`);
  const schema = o.schema || nodePath.join(home, "Work/projects/astra-webui/src/lib/canvas-schema.ts");

  const parser = readParserSets(schema); // exits 2 before anything is rendered or written
  verifyAgainstData(parser);
  const n = parser.types.length;

  const { targets, missingSkills, ambiguousSkills } = planTargets(home, renderHarness(n), renderSoul(n));
  const drift = [];
  const changed = [];
  const skipped = [];
  for (const t of targets) {
    if (t.skip) {
      skipped.push({ path: t.path, reason: t.skip });
      continue;
    }
    if (o.check) {
      const onDisk = t.original === null ? null : fs.readFileSync(t.path, "utf8");
      if (onDisk === null) drift.push({ path: t.path, reason: "file missing" });
      else if (onDisk !== t.desired) drift.push({ path: t.path, reason: onDisk.includes(MARKERS[t.kind][0]) ? "block differs" : "no markers" });
    } else if (t.desired !== t.original) {
      changed.push(t);
    }
  }

  let ok = true;
  if (o.check) {
    ok = drift.length === 0;
  } else {
    backup(home, changed, o.backup);
    for (const t of changed) writeAtomic(t.path, t.desired);
  }

  const evaluated = targets.length - skipped.length;
  if (o.json) {
    process.stdout.write(
      JSON.stringify({
        ok,
        changed: changed.map((t) => t.path),
        skipped,
        drift,
        missingSkills,
        ambiguousSkills,
        blockTypes: n,
      }) + "\n",
    );
  } else {
    for (const s of skipped) process.stdout.write(`skip ${s.path}: ${s.reason}\n`);
    for (const name of missingSkills) process.stdout.write(`missing skill: ${name}\n`);
    for (const name of ambiguousSkills) process.stdout.write(`ambiguous skill: ${name}\n`);
    if (o.check) {
      for (const d of drift) process.stdout.write(`DRIFT ${d.path}: ${d.reason}\n`);
      process.stdout.write(ok ? `canvas surfaces: in sync (${evaluated} targets)\n` : `canvas surfaces: ${drift.length} drift (${evaluated} targets)\n`);
    } else {
      process.stdout.write(`canvas surfaces: ${changed.length} changed, ${skipped.length} skipped, ${missingSkills.length} missing skills, ${ambiguousSkills.length} ambiguous (${evaluated} targets)\n`);
    }
  }
  process.exit(o.check && drift.length ? 1 : 0);
}

main();