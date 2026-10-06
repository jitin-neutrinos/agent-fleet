#!/usr/bin/env node
// rules/canvas-surface-sync.check.mjs — assert-based self-check for rules/canvas-surface-sync.mjs.
// node:assert/strict, no framework. Each scenario runs against a throw-away copy of fake-home
// under tmp-run-<pid>/ (deleted at the end). Nothing outside this worktree is written.
import assert from "node:assert/strict";
import fs from "node:fs";
import nodePath from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
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

const HERE = nodePath.dirname(fileURLToPath(import.meta.url));
const GEN = nodePath.join(HERE, "canvas-surface-sync.mjs");
const FAKE = nodePath.join(HERE, "..", "fake-home");
const SCHEMA = "/home/notjitin/Work/projects/astra-webui/src/lib/canvas-schema.ts";
const TMP = nodePath.join(HERE, "..", `tmp-run-${process.pid}`);
const HARNESS_FILES = [".claude/CLAUDE.md", ".gemini/GEMINI.md", ".config/opencode/AGENTS.md", "AGENTS.md"];
const ALL_TYPES = Object.keys(TYPES);
const LISTED_SKILLS = Object.entries(SKILL_GROUPS).flatMap(([kind, names]) => names.map((n) => [kind, n]));
let passed = 0;

// ---------------------------------------------------------------- helpers
function run(args) {
  try {
    const out = execFileSync(process.execPath, [GEN, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { status: 0, stdout: out, stderr: "" };
  } catch (e) {
    return { status: e.status ?? -1, stdout: e.stdout ?? "", stderr: e.stderr ?? "" };
  }
}

const sync = (home, ...args) => run(["--home", home, "--schema", SCHEMA, ...args]);

function freshHome(name) {
  const dir = nodePath.join(TMP, name);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.cpSync(FAKE, dir, { recursive: true });
  return dir;
}

function shaTree(root) {
  const out = {};
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
      if (e.name === "backups") continue;
      const p = nodePath.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else out[nodePath.relative(root, p)] = createHash("sha256").update(fs.readFileSync(p)).digest("hex");
    }
  };
  walk(root);
  return out;
}

const read = (home, rel) => fs.readFileSync(nodePath.join(home, rel), "utf8");
const blockOf = (text, start, end) => {
  const i = text.indexOf(start);
  const j = text.indexOf(end, i);
  return i < 0 || j < 0 ? null : text.slice(i, j + end.length);
};

// a copy of the real parser with the BLOCK_TYPES / CHART_KINDS literal edited
function syntheticSchema(name, edit) {
  const src = fs.readFileSync(SCHEMA, "utf8");
  const file = nodePath.join(TMP, `${name}.ts`);
  fs.writeFileSync(file, edit(src));
  return file;
}

function findSkill(home, name) {
  const files = execFileSync("find", [nodePath.join(home, ".hermes/skills"), "-name", "SKILL.md"], { encoding: "utf8" });
  for (const f of files.trim().split("\n").sort()) {
    const head = fs.readFileSync(f, "utf8").split("\n", 15).find((l) => l.startsWith("name:"));
    if (head && head.slice(5).trim().replace(/^["']|["']$/g, "") === name) return f;
  }
  return null;
}

function within(name, fn) {
  fn();
  passed++;
  process.stdout.write(`ok ${name}\n`);
}

fs.rmSync(TMP, { recursive: true, force: true });
fs.mkdirSync(TMP, { recursive: true });
try {
  // ================================================================ 1. parser truth, fail loudly
  // rewrite the quoted names of one `const X = new Set([ … ]);` literal in the real parser source
  const edited = (src, constName, mutate) => {
    const start = src.indexOf(`const ${constName} = new Set([`);
    const end = src.indexOf("]);", start);
    const names = [...src.slice(start, end).matchAll(/"([^"]+)"/g)].map((m) => m[1]);
    return src.slice(0, start) + `const ${constName} = new Set([\n  ${mutate(names).map((n) => `"${n}"`).join(", ")}\n` + src.slice(end);
  };

  within("1a-parser-rejects-extra-block-type", () => {
    const p = syntheticSchema("extra-type", (s) => edited(s, "BLOCK_TYPES", (n) => [...n, "sparkline"]));
    const r = run(["--home", freshHome("h1a"), "--schema", p]);
    assert.equal(r.status, 2, `expected exit 2, got ${r.status}`);
    assert.match(r.stderr + r.stdout, /sparkline/);
    assert.match(r.stderr + r.stdout, /BLOCK_TYPES/);
  });

  within("1b-parser-rejects-missing-block-type", () => {
    const p = syntheticSchema("missing-type", (s) => edited(s, "BLOCK_TYPES", (n) => n.filter((x) => x !== "terminal")));
    const r = run(["--home", freshHome("h1b"), "--schema", p]);
    assert.equal(r.status, 2);
    assert.match(r.stderr + r.stdout, /terminal/);
  });

  within("1c-parser-rejects-changed-chart-kinds", () => {
    const p = syntheticSchema("changed-charts", (s) => edited(s, "CHART_KINDS", (n) => n.map((x) => (x === "sankey" ? "sankeychart" : x))));
    const r = run(["--home", freshHome("h1c"), "--schema", p]);
    assert.equal(r.status, 2);
    assert.match(r.stderr + r.stdout, /sankeychart/);
    assert.match(r.stderr + r.stdout, /CHART_KINDS/);
  });

  within("1d-missing-schema-exits-2", () => {
    const r = run(["--home", freshHome("h1d"), "--schema", nodePath.join(TMP, "nope.ts")]);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /schema not found/);
  });

  within("1e-parser-mismatch-also-exits-2-in-check-mode", () => {
    const p = syntheticSchema("check-mode", (s) => edited(s, "BLOCK_TYPES", (n) => [...n, "sparkline"]));
    const r = run(["--home", freshHome("h1e"), "--schema", p, "--check"]);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /sparkline/);
    assert.doesNotMatch(r.stdout, /DRIFT/); // it must bail before any target work
  });

  // ================================================================ 2. --check on the untouched fake home
  within("2-check-on-untouched-home-lists-drift", () => {
    const home = freshHome("h2");
    const r = sync(home, "--check");
    assert.equal(r.status, 1);
    const lines = r.stdout.trim().split("\n");
    const driftLines = lines.filter((l) => l.startsWith("DRIFT "));
    for (const f of HARNESS_FILES.slice(0, 3)) {
      const line = driftLines.find((l) => l.startsWith(`DRIFT ${nodePath.join(home, f)}:`));
      assert.ok(line, `no DRIFT line for ${f}`);
      assert.match(line, /block differs$/);
    }
    for (const f of ["AGENTS.md", ".hermes/SOUL.md"]) {
      const line = driftLines.find((l) => l.startsWith(`DRIFT ${nodePath.join(home, f)}:`));
      assert.ok(line, `no DRIFT line for ${f}`);
      assert.match(line, /no markers$/);
    }
    const skillDrift = driftLines.filter((l) => l.includes("/SKILL.md: no markers"));
    assert.ok(skillDrift.length >= 1, "no skill DRIFT line");
    assert.equal(driftLines.length, 61, "expected every target to drift");
    assert.ok(!fs.existsSync(nodePath.join(home, ".hermes/backups")), "--check must not create backups");
  });

  // ================================================================ 3. write then idempotent
  const home3 = freshHome("h3");
  const before = shaTree(home3);
  within("3a-write-then-check-is-in-sync", () => {
    const w = sync(home3);
    assert.equal(w.status, 0);
    assert.match(w.stdout, /61 changed/);
    const c = sync(home3, "--check");
    assert.equal(c.status, 0);
    assert.match(c.stdout, /in sync \(61 targets\)/);
  });
  within("3b-second-write-changes-nothing", () => {
    const mid = shaTree(home3);
    const w = sync(home3, "--json");
    assert.equal(w.status, 0);
    assert.deepEqual(JSON.parse(w.stdout).changed, []);
    assert.deepEqual(shaTree(home3), mid);
    const c = sync(home3, "--check");
    assert.equal(c.status, 0);
  });

  // ================================================================ 4. harness block content
  within("4-harness-block-content-and-size", () => {
    // Pinned so a silent count change cannot pass the suite. Bump this WITH the
    // parser's BLOCK_TYPES and the data module in the same commit.
    assert.equal(EXPECTED_BLOCK_TYPES, 49);
    for (const f of HARNESS_FILES) {
      const b = blockOf(read(home3, f), "<!-- astra-canvas:start -->", "<!-- astra-canvas:end -->");
      assert.ok(b, `no harness block in ${f}`);
      assert.ok(b.length <= 2400, `${f}: block is ${b.length} chars`);
      assert.ok(b.includes(`${EXPECTED_BLOCK_TYPES} block types (closed set)`), `${f}: no type count`);
      for (const t of ALL_TYPES) assert.ok(b.includes("`" + t + "`"), `${f}: missing type ${t}`);
      for (const k of CHART_KINDS) assert.ok(b.includes("`" + k + "`"), `${f}: missing chart kind ${k}`);
      for (const [name] of RECIPES) assert.ok(b.includes(`**${name}:**`), `${f}: missing recipe ${name}`);
      assert.equal(GROUPS.flatMap(([, t]) => t).length, ALL_TYPES.length);
      for (const g of GROUPS) for (const t of g[1]) assert.ok(b.includes(g[0]) && b.includes("`" + t + "`"));
      assert.equal(blockOf(read(home3, f), "<!-- astra-canvas:start -->", "<!-- astra-canvas:end -->"), b);
    }
    for (const rule of HARNESS_RULES) assert.ok(blockOf(read(home3, HARNESS_FILES[0]), "<!-- astra-canvas:start -->", "<!-- astra-canvas:end -->").includes(rule));
    assert.doesNotMatch(read(home3, ".claude/CLAUDE.md"), /26 block types/);
    assert.doesNotMatch(read(home3, ".gemini/GEMINI.md"), /26 block types/);
    assert.doesNotMatch(read(home3, ".config/opencode/AGENTS.md"), /26 block types/);
    assert.doesNotMatch(read(home3, "AGENTS.md"), /26 block types/);
  });

  // ================================================================ 5. SOUL.md migration
  within("5-soul-table-is-one-contiguous-run", () => {
    const soul = read(home3, ".hermes/SOUL.md");
    const b = blockOf(soul, "<!-- astra-canvas:soul:start -->", "<!-- astra-canvas:soul:end -->");
    assert.ok(b, "no soul block");
    const lines = b.split("\n");
    const sep = lines.indexOf("|---|---|---|");
    assert.ok(sep > 0, "no table header separator");
    let rows = 0;
    let line = sep + 1;
    for (; line < lines.length && /^\| `/.test(lines[line]); line++) rows++;
    assert.equal(rows, EXPECTED_BLOCK_TYPES, `expected ${EXPECTED_BLOCK_TYPES} table rows, got ${rows}`);
    assert.equal(lines[line], "", `prose line right after the table: ${lines[line]}`);
    const types = lines.slice(sep + 1, sep + 1 + rows).map((l) => l.slice(3, l.indexOf("`", 3)));
    assert.deepEqual(types, GROUPS.flatMap(([, t]) => t));
    assert.doesNotMatch(soul, /Anti-slop \(fragmentation/);
    for (const r of SOUL_RULES) assert.ok(b.includes(r), "soul rule missing");
    for (const k of CHART_KINDS) assert.ok(b.includes("`" + k + "`"));
    for (const [name] of RECIPES) assert.ok(b.includes(`**${name}:**`));
    assert.ok(b.includes('`chart:"graph"` is NOT a chart'));
    assert.match(soul, /\{tone:info\\\|warn/); // pipes inside a shape cell are escaped
  });

  within("5b-soul-outside-the-section-is-byte-identical", () => {
    // The fake SOUL's `## Generative UI` section runs to EOF, so a following section is appended
    // first — otherwise "everything after the next heading" would be empty and the check vacuous.
    const home = freshHome("h5b");
    const soulFile = nodePath.join(home, ".hermes/SOUL.md");
    const LATER = "\n## Later section\n\nuntouched body text\n";
    fs.appendFileSync(soulFile, LATER);
    const orig = fs.readFileSync(soulFile, "utf8");
    const at = orig.indexOf("## Generative UI");
    const next = orig.indexOf("\n## ", at + 1);
    assert.ok(next > at, "test setup: no later heading");
    const prefix = orig.slice(0, at);
    const suffix = orig.slice(next + 1);
    const w = sync(home);
    assert.equal(w.status, 0);
    const now = fs.readFileSync(soulFile, "utf8");
    const marker = "<!-- astra-canvas:soul:start -->\n";
    assert.ok(now.startsWith(prefix + marker), "text before the section changed");
    assert.ok(now.endsWith(suffix), "text after the next heading changed");
    assert.equal(suffix, "## Later section\n\nuntouched body text\n");
    assert.equal(now.slice(0, now.indexOf(marker)), prefix); // not one byte more, not one byte less
    assert.equal(blockOf(now, marker.trimEnd(), "<!-- astra-canvas:soul:end -->").endsWith("<!-- astra-canvas:soul:end -->"), true);
    assert.equal(sync(home, "--check").status, 0);
  });

  // ================================================================ 6. skills
  within("6a-skills-gain-one-correct-block", () => {
    const home = freshHome("h6");
    const w = sync(home);
    assert.equal(w.status, 0);
    const absent = LISTED_SKILLS.filter(([, name]) => !findSkill(home, name));
    assert.deepEqual(absent, [], "every listed skill should exist in the fake home");
    for (const [kind, name] of LISTED_SKILLS) {
      const rel = nodePath.relative(home, findSkill(home, name));
      const orig = read(FAKE, rel);
      const now = fs.readFileSync(nodePath.join(home, rel), "utf8");
      assert.equal(now.split("<!-- canvas-output:start -->").length - 1, 1, `${name}: block count`);
      const b = blockOf(now, "<!-- canvas-output:start -->", "<!-- canvas-output:end -->");
      assert.ok(b.endsWith(STANZAS[kind] + "\n<!-- canvas-output:end -->"), `${name}: wrong stanza`);
      assert.ok(now.startsWith(orig.replace(/\s+$/, "") + "\n\n"), `${name}: content above the marker changed`);
      assert.ok(now.trimEnd().endsWith("<!-- canvas-output:end -->"), `${name}: block not last`);
    }
  });

  within("6b-second-run-adds-no-second-block", () => {
    const home = nodePath.join(TMP, "h6");
    const before = shaTree(home);
    const w = sync(home, "--json");
    assert.equal(w.status, 0);
    assert.deepEqual(JSON.parse(w.stdout).changed, []);
    assert.deepEqual(shaTree(home), before);
  });

  within("6c-unlisted-skill-is-byte-identical", () => {
    for (const name of ["caveman", "humanizer"]) {
      const p = findSkill(nodePath.join(TMP, "h6"), name);
      assert.deepEqual(fs.readFileSync(p), fs.readFileSync(findSkill(FAKE, name)), name);
    }
  });

  within("6d-missing-and-ambiguous-skills-are-reported", () => {
    const home = nodePath.join(TMP, "h6-min");
    fs.mkdirSync(nodePath.join(home, ".hermes/skills/research/arxiv"), { recursive: true });
    fs.cpSync(findSkill(FAKE, "arxiv"), nodePath.join(home, ".hermes/skills/research/arxiv/SKILL.md"));
    fs.cpSync(findSkill(FAKE, "arxiv"), nodePath.join(home, ".hermes/skills/research/zzz-arxiv/SKILL.md")); // same frontmatter name
    const r = sync(home, "--json");
    assert.equal(r.status, 0);
    const j = JSON.parse(r.stdout);
    assert.deepEqual(j.ambiguousSkills, ["arxiv"]);
    assert.equal(j.missingSkills.length, LISTED_SKILLS.length - 1);
    assert.ok(!j.missingSkills.includes("arxiv"));
    assert.ok(j.missingSkills.includes("xurl"));
    assert.ok(fs.readFileSync(nodePath.join(home, ".hermes/skills/research/arxiv/SKILL.md"), "utf8").includes("canvas-output"));
    assert.ok(!fs.readFileSync(nodePath.join(home, ".hermes/skills/research/zzz-arxiv/SKILL.md"), "utf8").includes("canvas-output"));
    assert.match(sync(home).stdout, /ambiguous skill: arxiv/);
  });

  // ================================================================ 7. backups
  within("7a-backup-holds-the-original-bytes", () => {
    const home = freshHome("h7");
    const originals = shaTree(home);
    const w = sync(home);
    assert.equal(w.status, 0);
    const root = nodePath.join(home, ".hermes/backups/canvas-sync");
    const runs = fs.readdirSync(root);
    assert.equal(runs.length, 1, "one run dir per run");
    const files = fs.readdirSync(nodePath.join(root, runs[0]));
    assert.equal(files.length, Object.keys(originals).length - 2, "one backup per changed file");
    for (const f of files) {
      const rel = f.split("__").join("/");
      assert.equal(createHash("sha256").update(fs.readFileSync(nodePath.join(root, runs[0], f))).digest("hex"), originals[rel], rel);
      assert.notEqual(createHash("sha256").update(fs.readFileSync(nodePath.join(home, rel))).digest("hex"), originals[rel], `${rel} was not written`);
    }
    assert.ok(files.includes(".claude__CLAUDE.md") && files.includes(".hermes__SOUL.md"));
  });

  within("7b-check-creates-no-backups-and-no-backup-flag-skips-them", () => {
    const home = freshHome("h7b");
    assert.equal(sync(home, "--check").status, 1);
    assert.ok(!fs.existsSync(nodePath.join(home, ".hermes/backups")), "--check wrote backups");
    assert.equal(sync(home, "--no-backup").status, 0);
    assert.ok(!fs.existsSync(nodePath.join(home, ".hermes/backups")), "--no-backup wrote backups");
    assert.equal(sync(home, "--check").status, 0);
  });

  within("7c-after-22-runs-only-20-run-dirs-remain", () => {
    const home = freshHome("h7c");
    const victim = nodePath.join(home, ".hermes/skills/research/arxiv/SKILL.md");
    const pristine = fs.readFileSync(victim);
    const root = nodePath.join(home, ".hermes/backups/canvas-sync");
    for (let i = 0; i < 22; i++) {
      fs.writeFileSync(victim, pristine); // force this file to change again on every later run
      const r = sync(home);
      assert.equal(r.status, 0);
      assert.match(r.stdout, i === 0 ? /^canvas surfaces: 61 changed/ : /^canvas surfaces: 1 changed/);
    }
    const runs = fs.readdirSync(root).sort();
    assert.equal(runs.length, 20, `expected 20 run dirs, got ${runs.length}`);
    assert.ok(fs.existsSync(nodePath.join(root, runs[19], ".hermes__skills__research__arxiv__SKILL.md")));
    assert.equal(sync(home, "--check").status, 0);
  });

  // ================================================================ 8. missing parent directory
  within("8-missing-parent-dir-is-skipped-not-fatal", () => {
    const home = freshHome("h8");
    fs.rmSync(nodePath.join(home, ".gemini"), { recursive: true });
    const w = sync(home, "--json");
    assert.equal(w.status, 0);
    const j = JSON.parse(w.stdout);
    assert.deepEqual(j.skipped, [{ path: nodePath.join(home, ".gemini/GEMINI.md"), reason: "no parent directory" }]);
    assert.match(sync(home).stdout, new RegExp(`^skip ${nodePath.join(home, ".gemini").replace(/[.]/g, "\\.")}/GEMINI.md: no parent directory$`, "m"));
    assert.ok(!fs.existsSync(nodePath.join(home, ".gemini")), "a skipped target must not create its directory");
    assert.equal(sync(home, "--check").status, 0);
  });

  within("8b-missing-home-agents-md-is-skipped", () => {
    const home = freshHome("h8b");
    fs.rmSync(nodePath.join(home, "AGENTS.md"));
    const j = JSON.parse(sync(home, "--json").stdout);
    assert.deepEqual(j.skipped, [{ path: nodePath.join(home, "AGENTS.md"), reason: "file missing" }]);
    assert.ok(!fs.existsSync(nodePath.join(home, "AGENTS.md")), "AGENTS.md must not be created");
    assert.ok(read(home, ".hermes/SOUL.md").includes("<!-- astra-canvas:soul:start -->"), "SOUL.md must still be synced");
    assert.equal(sync(home, "--check").status, 0);
  });

  // ================================================================ 9. empty home
  within("9-empty-home-does-nothing", () => {
    const home = nodePath.join(TMP, "h9");
    fs.mkdirSync(home, { recursive: true });
    const r = sync(home, "--json");
    assert.equal(r.status, 0);
    const j = JSON.parse(r.stdout);
    assert.deepEqual(j.changed, []);
    assert.deepEqual(j.drift, []);
    assert.equal(j.skipped.length, 5);
    assert.equal(j.blockTypes, EXPECTED_BLOCK_TYPES);
    assert.match(sync(home, "--check").stdout, /in sync \(0 targets\)/);
    assert.equal(sync(home, "--check").status, 0);
    assert.deepEqual(fs.readdirSync(home), [], "nothing may be written into an empty home");
    assert.equal(run(["--home", nodePath.join(TMP, "no-such-home"), "--schema", SCHEMA]).status, 2);
  });

  // ================================================================ 10. json shape / usage
  within("10-json-object-has-every-key", () => {
    const home = freshHome("h10");
    const j = JSON.parse(sync(home, "--check", "--json").stdout);
    assert.deepEqual(Object.keys(j), ["ok", "changed", "skipped", "drift", "missingSkills", "ambiguousSkills", "blockTypes"]);
    assert.equal(j.ok, false);
    assert.equal(j.drift.length, 61);
    assert.equal(sync(home, "--json").status, 0);
    assert.equal(JSON.parse(sync(home, "--json").stdout).ok, true);
    assert.equal(run(["--home", home, "--schema", SCHEMA, "--nope"]).status, 2);
    assert.equal(run(["--home"]).status, 2);
    assert.equal(run(["--home", home]).status, 2); // default --schema under $HOME/Work/… is absent here
  });
} finally {
  fs.rmSync(TMP, { recursive: true, force: true });
}

process.stdout.write(`canvas-surface-sync.check: ${passed} assertions passed\n`);