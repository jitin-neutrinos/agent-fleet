// replay-stored-message.mjs — replay the message that ACTUALLY failed to render.
//
// Usage (from the astra-webui repo root, so the TS loader resolves):
//   node --import ./scripts/ts-resolve.mjs <path-to>/replay-stored-message.mjs <session_id> [message_id|last]
//
// Why: a hand-typed approximation of "what the model emitted" tests the wrong
// thing and passes while the live case stays broken. This pulls the real stored
// text and runs it through the consumer's own parser, which is the only way to
// separate "I emitted malformed JSON" from "the payload is fine and the RENDER
// failed" — two failures that look identical to the user.
//
// Reads state.db read-only (never mutates the store), writes the extracted text
// to a scratch file, and reports:
//   • message id + byte size + block count        <- size is a load-bearing input
//   • splitCanvasBlocks in BOTH modes            <- streaming vs settled differ
//   • per-block validateBlock OK/REJECTED
//   • the exact live-path planner result          <- spanning-only, by design
//
// GOTCHA this encodes: validateBlock is a COERCER that returns a normalised
// block or null. It is NOT a boolean predicate — `if (!validateBlock(b))`
// reads truthy on every block and reports a fully valid card as 100% invalid.

import { DatabaseSync } from "node:sqlite";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { pathToFileURL } from "node:url";

const REPO = process.env.ASTRA_WEBUI ?? join(homedir(), "Work/projects/astra-webui");
const DB = process.env.HERMES_HOME
  ? join(process.env.HERMES_HOME, "state.db")
  : join(homedir(), ".hermes/state.db");
const SCRATCH = process.env.SCRATCH ?? join(homedir(), ".hermes/cache/scratch");

const [sessionId, which = "last"] = process.argv.slice(2);
if (!sessionId) {
  console.error("usage: replay-stored-message.mjs <session_id> [message_id|last]");
  process.exit(2);
}

const db = new DatabaseSync(`file:${DB}?mode=ro`, { readOnly: true });
const row =
  which === "last"
    ? db
        .prepare(
          `SELECT id, role, content FROM messages
           WHERE session_id = ? AND role = 'assistant' AND content LIKE '%astra-canvas%'
           ORDER BY id DESC LIMIT 1`,
        )
        .get(sessionId)
    : db.prepare("SELECT id, role, content FROM messages WHERE session_id = ? AND id = ?").get(sessionId, Number(which));
if (!row) {
  console.error("no matching message with an astra-canvas fence");
  process.exit(2);
}

mkdirSync(SCRATCH, { recursive: true });
const file = join(SCRATCH, `replay-msg-${row.id}.md`);
writeFileSync(file, row.content);

const fences = (row.content.match(/`{3,}astra-canvas/g) || []).length;
const bytes = Buffer.byteLength(row.content, "utf8");
console.log(`message ${row.id}  role=${row.role}`);
console.log(`  ${bytes} bytes (${(bytes / 1024).toFixed(1)} KB)  fences=${fences}`);
console.log(`  written: ${file}`);

let m;
try {
  m = await import(pathToFileURL(join(REPO, "src/lib/canvas-schema.ts")).href);
} catch (e) {
  console.error("\nCould not load canvas-schema.ts.");
  console.error("Run this from the repo root so the TS loader resolves:");
  console.error("  node --import ./scripts/ts-resolve.mjs <this file> " + process.argv.slice(2).join(" "));
  console.error("cause:", e.message);
  process.exit(3);
}

const show = (parts) =>
  parts
    .map((p) => (p.kind === "canvas" ? `canvas(${p.spec?.blocks?.length} blocks)` : `md(${p.text.length})`))
    .join(" ");

for (const streaming of [false, true]) {
  const parts = m.splitCanvasBlocks(row.content, streaming);
  const spec = parts.find((p) => p.kind === "canvas")?.spec;
  const n = spec?.blocks?.length ?? 0;
  console.log(`\nsplitCanvasBlocks(streaming=${streaming}): ${show(parts)}`);
  if (!n) {
    console.log("  NO CARD — the payload did not parse; this IS an emission bug.");
    continue;
  }
  let bad = 0;
  spec.blocks.forEach((b, i) => {
    if (m.validateBlock(structuredClone(b))) return;
    bad++;
    console.log(`  REJECTED block ${i}: ${b.type}`);
  });
  console.log(`  blocks=${n} rejected=${bad}${bad ? "" : "  <- payload is VALID"}`);
}

// The live turn planner only extracts SPANNING fences (a fence opening in one
// segment and closing in another). A CONTAINED fence returns 0 canvases by
// design so trailing prose stays below the card. A single-segment call here
// reporting 0 is correct behaviour, not a failure.
try {
  const plan = m.planTurnCanvases([row.content]);
  console.log(`\nplanTurnCanvases(single segment): canvases=${plan.canvases.length} (0 is correct for a contained fence)`);
} catch (e) {
  console.log("\nplanTurnCanvases threw:", e.message);
}

// A prefix ending inside the payload must be WITHHELD, not half-painted.
const at = row.content.indexOf("```astra-canvas") + 400;
const prefix = row.content.slice(0, at);
console.log(`prefix ending mid-payload: hasCanvas=${m.hasCanvas(prefix)} (false = the reveal guard is working)`);

if (n > 10 || bytes > 6144) {
  console.log(`\nSIZE: ${n} blocks / ${(bytes / 1024).toFixed(1)} KB is a large card.`);
  console.log("If every block validated and nothing painted, the payload is not the cause.");
  console.log("Prefer several focused sibling cards over one monolith regardless.");
}
