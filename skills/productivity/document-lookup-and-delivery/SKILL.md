---
name: document-lookup-and-delivery
description: "Find, verify and deliver a document the user names."
version: 1.0.0
author: Hermes curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [document-lookup, file-delivery, media, pdf, version-latest]
    category: productivity
---

# Finding and delivering a named document

## When to Use

- "Send me the latest version of X", "that report from last week", "the v4
  stakeholder PDF" — the user names an artifact from memory, not by path.
- Any request to locate a specific file among a versioned series, confirm which
  copy is current, and hand it over in chat.
- NOT for: creating a new document (use the `pdf`/`docx` skills), or for
  searching a codebase (`search_files` on a repo).

For requests like "send me the latest v4 stakeholder PDF" or "that letter from
last month" — the user names the artifact from memory, not by path. The job is
locate, confirm it is the right and newest copy, verify its identity, hand it
over.

## Procedure

1. **Match the filename, not the contents.** Grepping file *contents* for a
   document title hits thousands of unrelated files (datasets, vocabularies,
   evaluation fixtures). Search by name.
2. **Walk the likely homes, newest first.** `~/uploads/` (chat-delivery
   copies), `~/Downloads/`, `~/Documents/`, then the owning project directory.
   `ls -la` the candidate directory filtered on the document stem so you see
   the whole version series at once — you need the set, not one file.
3. **Scope filesystem searches to one directory.** A broad
   `search_files(target='files')` over `$HOME` is refused as an unbounded
   traversal; `find <dir> -maxdepth 4 -iname '*stem*'` from `terminal` works.
   Always pass a depth limit.
4. **Establish "latest" from mtime, never from the version label.** Read the
   timestamps across the whole series. A later write to a lower-numbered file
   is still the freshest copy, and two versions can be minutes apart.
5. **Verify identity before sending.** Never deliver a file you matched only
   by filename. For a PDF run `pdfinfo` (title, producer, page count), then
   rasterize page 1 and read it — confirm title, version, date, and subject.
6. **Deliver** with a bare `MEDIA:/absolute/path` line on its own line, never
   in a code fence or inside a sentence. See `telegram-media-delivery` for the
   container-path caveat.
7. **Report the hash and size** (`sha256sum`, `stat`) alongside the MEDIA line
   so the receiver can confirm which copy they got.
8. **Clean rasters out of the scratch dir** — never `~/.hermes/cache/*`
   (read-only on some backends), never system `/tmp`.

## Pitfalls

- **`vision_analyze` cannot read a `.pdf` path directly** — it rejects it as
  an unrecognized image. Render first: `pdftoppm -f 1 -l 2 -r 110 -png
  in.pdf outprefix`, then pass the PNG.
- **A text-layer-less PDF is not a broken PDF.** `read_file` raises
  `NeedsOcrError` naming the pages needing OCR — that tells you the file is
  image-only. `pdfinfo` still works, and the rendered-page vision read is the
  way to inspect it. Do not report it as unreadable or corrupt.
- **`pdftoppm` output is `outprefix-01.png`** (zero-padded); glob with
  `outprefix-0*` when cleaning up.
- **Content grep over `$HOME` returns permission-denied noise** on service
  data directories. Scope to a candidate directory instead of filtering the
  noise after the fact.
- **Version labels lie about recency.** Compare mtimes across every sibling in
  the series; if the user names a version, confirm it is actually the newest
  rather than assuming their label is current.
- **When the ask is to deliver, deliver — don't retype.** Do not paste the
  document's contents into the reply. Send the file and report what you
  verified about it; offer to extract a section only if asked.
- **Delete your scratch renders before finishing**, so the next session does
  not find them and mistake them for source artifacts.
