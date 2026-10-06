---
name: docs-ingestion-pipelines
description: Scrape docs portals into CSV/DB for AI retrieval pipelines.
---

# Docs ingestion pipelines (scrape → CSV → AI-ready data)

Covers: scraping documentation portals (ClickHelp recipe in references/clickhelp.md), RAG/ingestion corpus building, and scheduled self-healing scraper containers.

## Standing rules

- Scraper is stdlib-only (urllib, html.parser, csv, json, zoneinfo, concurrent.futures). No pip deps means the Docker image is `python:X-slim` + one COPY line — no requirements.txt to rot.
- A login-walled SPA does not mean the content is private. Probe for server-rendered endpoints before reaching for headless browsers; docs portals almost always expose one for SEO. ClickHelp: see references/clickhelp.md.
- Change detection = sitemap `lastmod` diff against a stored state file. Never re-scrape the corpus to find changes; never re-derive data you can diff.
- Scheduling inside a container: NO cron. Run one forever-loop: on startup, run immediately if the last successful run predates today's scheduled time (self-healing catch-up after downtime), then sleep until tomorrow's run time. `restart: unless-stopped` + a healthcheck that reads the last-run status file (<48h old).
- Write artifacts atomically (tmp file + `os.replace`) — a run dying mid-write must never corrupt the previous CSV/state.
- Leave an assert-based selftest behind: synthetic HTML covering every page shape + one check against a real fetched page. Portal page shapes are discovered by contact, not guessed.
- Verify the article endpoint with curl BEFORE writing the extractor: confirm real body text is present, not just HTTP 200 (error pages and empty shells also return 200).

## Procedure

1. **Discover** — sitemap index → per-publication sitemaps → every topic with `lastmod`. Publication id = sitemap filename suffix. This enumerates the full corpus by construction; link-crawling the SPA nav misses most of it.
2. **Probe** — curl one article endpoint from the sitemap. Check content text is in the HTML. Record the content container boundaries.
3. **Extract** — HTMLParser subclass → markdown-ish text. The pitfalls in the next section each cost a debugging cycle; read them before writing the parser, not after it fails.
4. **Store** — per-topic cache files (sanitized pub/slug path, no spaces) + a state file (key → lastmod, title, links, fetched_at). Rebuild the CSV/dataset from cache + state so it can be recompiled offline at any time.
5. **Classify failures** — a page with a `<title>` but no body is a real placeholder topic: record it with empty content, it is not a retry candidate. Only fail (and leave for next run) when there is no title at all.
6. **Log** — JSON-lines run log with size-capped rotation + a last-run status file carrying status (ok/partial/failed), counts, and first-N failures. Health checks and humans both read the status file.
7. **Harden before trusting green** — the four audit-grade guards (see Corruption guards below) cost ~20 lines total and each closes a silent-data-loss path. An unguarded scraper reports `ok` while destroying its corpus; the guards exist because every one of these failure modes actually happened or was reproduced in a sandbox.

## HTMLParser pitfalls (each verified the hard way)

- **Skip counters leak on empty elements.** If you increment a skip counter on an element class (scripts, icon anchors) and only decrement it in one endtag branch, `<a class="iconlink"></a>` increments on open and its `</a>` matches a different branch — skip never returns to 0 and the rest of the page silently produces only markers (`****`, bare `-`). Decrement in the endtag handler whenever skip > 0 and the tag can open a skip, regardless of which branch handles it.
- **The parser never synthesizes end tags.** Loose trailing text after the last close tag never flushes — output ends early. Append a sentinel closing tag to the input before feeding (e.g. `body += "<footer></footer>"` when the real footer was cut off), or flush in `close()`.
- **Markers must survive mid-structure flushes.** Block boundaries (`<p>`, `<div>`) fire inside `<li>`, `<td>`, `<ul>` wrappers and wipe any `**`/`- ` prefix sitting in the main buffer. Keep structural markers in a separate `pending` list prepended to the buffer at flush time; clear it only when the structure closes.
- **`<pre>` blocks need an explicit emit.** No enclosing block-end flush follows `</pre>` in practice, so the buffered code block never reaches output. Emit it in the `</pre>` handler, and treat `<code>` inside `<pre>` as a no-op (backticks already balanced).
- **Test against a real page, not only synthetic samples.** Real portals have shapes your sample never exercises: mini-TOC sidebars, pages whose body is loose text with no `<h1>` (take the title from `<title>` then), genuinely empty placeholder pages. Synthetic samples catch parser logic; the real page catches page-shape assumptions.

## Corruption guards (audit-grade, add all four before the scraper is trusted)

- **Sanity floor before pruning.** Topics absent from the sitemap are pruned from state — so an upstream rename of the sitemap filename pattern yields an empty discovery, prunes everything, and rewrites the CSV to zero rows **while reporting ok**. Refuse to prune when `discovered < 80% of known`; assert the sitemap list is non-empty; log its length.
- **Failure-rate ceiling.** A status file written even on failed runs makes the healthcheck lie. Mark the run `failed` (not `partial`) and raise when failures exceed `max(5, 25%)` of the corpus — a portal-wide template change fails every page identically and must not pass as a bad day.
- **`lastmod` at full precision; content hash as change truth.** Truncating sitemap timestamps to dates permanently loses same-day second edits (date equal ⇒ skipped). Keep the full timestamp. But treat `lastmod` as only the cheap fetch pre-filter: bulk republishes stamp every topic and would force a full re-embed downstream — store `sha256(content)` per topic and let hash equality veto the change.
- **Shrink-guard on rebuild.** Refuse to overwrite the CSV/state when the new row count is < 80% of the previous — the last line of defense if a guard above is ever bypassed.

## Table extraction (markdown tables that downstream indexing can use)

- **Buffer cells into a row list; never flush per cell.** Flushing on every `<td>` emits each cell as its own block and destroys row structure — measured at 88% malformed table lines on a real portal before the fix. Emit one `| a | b |` line per `<tr>`, and a `|---|` separator after the first row so the output is a valid markdown table (downstream chunkers then keep the table intact as one unit).
- **Track skip state as a tag stack, not a counter.** A counter incremented for any element carrying a skip-class but decremented for only some tag types swallows the rest of the page when the class appears on an unexpected element — and the page still yields a valid title, so the truncation passes the fetch guard. Push the tag name on skip; pop only on the matching close.
- **Search the end boundary from the content start.** `text.find("<footer")` from offset 0 blanks the page when any footer appears before the content marker; search from `start`. Clear anchor href state unconditionally on `</a>` — a skipped element's close tag otherwise leaks the href onto later text.

## Downstream rebuild (corpus → AI index)

When an existing retrieval database consumes the corpus, don't fork a second pipeline: emit the consumer's input format from the cache + state (references/retrieval-rebuild.md), then run the consumer's own build stages. The CSV/cache contract keeps this a pure conversion step.

## Scheduling pattern (container)

- `TZ` env + `zoneinfo` in-process; container `restart: unless-stopped`.
- Healthcheck: parse the last-run status file, assert its timestamp is within ~2× the run interval and that status is not `failed`. If the healthcheck is a script flag (`--healthcheck`), share the exact logic with the run loop — a check reading only file mtime reports healthy through any failure.
- A no-change run should cost seconds (sitemap fetches only). This is what makes the catch-up-on-startup check safe to run every boot.
