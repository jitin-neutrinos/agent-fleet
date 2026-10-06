// Pre-emit validator for an Astra canvas spec.
//
// A malformed spec does not error — the parser degrades it to plain markdown, so the
// owner sees raw JSON and reports "the canvas is broken, it rendered as text" while
// the renderer is healthy. Run this on the candidate spec BEFORE sending it.
//
//   node validate-canvas-spec.mjs /path/to/spec.json
//
// Exit 0 = every block valid AND the wrapped fence yields exactly one card.
// Exit 2 = the file is not valid JSON (or no path given).  Exit 3 = a block is invalid
// or the card count is wrong (per-block INVALID lines are printed).
//
// Requires the astra-webui checkout; set ASTRA_WEBUI to override its path.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve, join } from "node:path";

const REPO = process.env.ASTRA_WEBUI ?? "/home/notjitin/Work/projects/astra-webui";
const specPath = process.argv[2];
if (!specPath) {
  console.error("usage: node validate-canvas-spec.mjs <spec.json>");
  process.exit(2);
}

const schemaPath = join(REPO, "src/lib/canvas-schema.ts");
const { validateBlock, splitCanvasBlocks } = await import(pathToFileURL(schemaPath).href);

const raw = readFileSync(resolve(specPath), "utf8");
let spec;
try {
  spec = JSON.parse(raw);
} catch (e) {
  console.log("JSON PARSE FAIL:", e.message);
  process.exit(2);
}

console.log("v:", spec.v, "| title:", spec.title ?? "(none)", "| blocks:", spec.blocks?.length ?? 0);

let bad = 0;
(spec.blocks ?? []).forEach((b, i) => {
  if (!validateBlock(structuredClone(b))) {
    bad++;
    console.log(`  BLOCK ${i} INVALID: ${b?.type ?? "(no type)"}`);
  }
});
console.log(bad === 0 ? "ALL BLOCKS VALID" : `${bad} INVALID BLOCK(S)`);

if (raw.includes("```")) {
  console.log("NOTE: payload contains ``` — emit it inside a 4-backtick fence.");
}

// A `code` block whose content has ``` is legal; only the OUTER fence must be longer.
const text = "```astra-canvas\n" + raw + "\n```";
const parts = splitCanvasBlocks(text, false);
const cards = parts.filter((p) => p.kind === "canvas").length;
console.log("splitCanvasBlocks ->", parts.map((p) => p.kind).join(","), "| canvas cards:", cards);

const ok = bad === 0 && cards === 1;
console.log(ok ? "OK — emit the fence exactly once." : "NOT EMITTABLE — fix the lines above.");
process.exit(ok ? 0 : 3);
