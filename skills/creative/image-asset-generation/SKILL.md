---
name: image-asset-generation
description: "Use when generating logos, icons, or favicons with AI."
---

# Image Asset Generation (agy + Nano Banana Pro)

Generate logo/icon/favicon brand images headlessly with `agy` (Antigravity CLI — its image generation = Nano Banana Pro), QA them visually, and package web size sets. This is Jitin's preferred route for logo work — prefer it over local diffusion.

## Procedure
1. **Write a prompt file per asset batch** (`scratch/prompt-logo-*.md`); use `templates/logo-prompt.md`. One run can produce several files (lockup candidates + icon variants).
2. **Generate headlessly:** `timeout 900 agy -p "$(cat scratch/prompt-x.md)" --print-timeout 12m --dangerously-skip-permissions --add-dir <repo> > scratch/agy-x.log 2>&1`, launched as `terminal(background=true, notify=true)`. Verified: files land at the ABSOLUTE paths named in the prompt and it replies with them; a multi-image batch takes ~1–4 min.
   - Without `--add-dir <workspace>`, agy has no active workspace and saves images to its own scratch dir (`~/.gemini/antigravity-cli/scratch/`) while SAYING so only in the log — read the reply text for the real save path, then copy the file to the project dir.
   - Generate as a separate terminal session; a run killed by the agent's own timeout (execute_code 300s cap) loses the turn mid-generation even though the model may still be working — background it with a generous print-timeout instead of re-running blind.
   - Long-icon/slow generations: if the log says 'print timeout ... turn in progress' with no file, re-run with a larger `--print-timeout`, don't assume the tool is broken.
3. **QA every image with `vision_analyze` before showing or shipping** — text spelling letter-by-letter, palette drift (any unspecified hue), gradient presence (if forbidden), centering, artifacts, plus a small-size rating.
4. **Iterate with the previous file as the reference** — name the prior PNG's path in the new prompt; the model follows the reference's geometry tightly, flaws included. To change only color treatment, regenerate "same mark, flat solid `<hex>`" against the approved file instead of re-describing from scratch.
5. **Stage → QC → swap:** keep candidates under versioned names (`candidate-N.png`, `vN-*.png`); write canonical names only after QA; back up replaced finals (`*.gradient.png` pattern) rather than deleting.
6. **Package favicons with the bundled script:** `bash scripts/favicon-set.sh <master.png> <out-dir>` → 16/32/48/180/192/512 + `.ico` + a pixel-doubled 32px preview. Check the preview with vision_analyze; done when the 32px reads as the mark, not a blob. Ship the SIZED set as the site favicon (16/32 + apple-touch 180 via `<link rel="icon">`/`rel="apple-touch-icon">`), never the multi-hundred-KB master — a 300KB favicon is a per-page-load tax on every visitor; keep the master for og:image and the repo.
7. **Let the user pick from candidates:** send lockups to the chat as media photos and ask for a pick. When the user states a brand correction (e.g. "no gradients"), apply it to ALL assets + docs in one pass, not one image.

## Prompt rules (what the model actually honors)
- Exact hex values with "use EXACTLY" for background, accents, text color.
- Text: "the only text is <word> — all lowercase, exactly N letters; no taglines, no .com, no extra symbols". Verify spelling in QA.
- **State these or they won't happen:** no-gradients (it defaults to two-color blends on any "modern tech" brief), flat/crisp edges (default is glow/soft render), stroke boldness.
- Numeric thickness specs are only directional — it undershoots on thin strokes and repeated passes stay thin. If small-size boldness matters, say "bold strokes", verify at pixel level, and expect to accept or hand-tune, not fully fix via prompt.
- Negative constraints worth listing: photorealism, 3D bevels, drop shadows, watermarks, extra letters, purple/magenta hues, light backgrounds, device mockups, frames.
- Demand PNG outputs at exact paths; "if one fails, retry once and continue; reply with the paths".

## Pitfalls
- **Never thicken strokes with `magick -morphology Dilate`** — at the radii needed it merges the glyph into its container (ring + mark became one blob; verified). Boldness comes from generation.
- Brand scope: for Jitin's product branding the standing rules are flat solid colors only (no gradients), cyan `#22d3ee` primary, teal `#14b8a6` sparing secondary, wordmark white `#f8fafc` on `#0a0a0f`. The jitinnair.com portfolio site itself uses gradients — don't strip those there; no-gradient is product-brand scope.
- Vision calls can 503 transiently — retry once before reacting; don't re-generate assets because a QA call failed. When the vision provider is out of quota (429/insufficient-balance), QA structurally instead of blocking: ImageMagick pixel probes (`magick <img> -format '%[pixel:p{x,y}]' info:-` at corners/center) verify background, accent color, and trim; dominant-color histogram (`-resize 64x64 txt:- | sort | uniq -c`) verifies the palette stayed in spec; `-trim +repage` produces a padding-free variant.
- When the model is told a spec (e.g. three-color palette), verify dominant colors match the spec — generated images drift (white background instead of tile color, extra hues) and pixel probes catch it without vision.

## Support files
- `templates/logo-prompt.md` — fill-in prompt skeleton that produced approved results.
- `scripts/favicon-set.sh` — master PNG → favicon size set + .ico + QA preview.
