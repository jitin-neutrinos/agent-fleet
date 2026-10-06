# ClickHelp documentation portal scraping

Verified against a live ClickHelp portal (Neutrinos, 2026-09); the URL/layout conventions below are standard ClickHelp, so try them first on any ClickHelp target.

## URL conventions

- Reader (human) URL: `/articles/#!{publication}/{slug}` — SPA shell, login-walled, returns a Login page to plain HTTP clients. Do not scrape this.
- Article content: `GET /article/{publication}/{slug}` — complete server-rendered HTML, **no auth**. This is the scraping endpoint.
- Anchor deep-links look like `/articles/{pub}/{slug}/a/{anchorId}`.

## Discovery via sitemaps

- Index: `/sitemaps/sitemap.xml` — lists `sitemaps/sitemap_publication_{pub}.xml` entries (one per publication, with lastmod).
- Each publication sitemap lists every topic: `<loc>` + `<lastmod>`. Slug = last path segment of `<loc>`.
- Publication id = filename after `sitemap_publication_`, minus `.xml`.
- robots.txt has a BOM quirk and the root redirects; go straight to the sitemap paths.

## Page layout (published article)

- Content sits between `<span id="__clhTop"></span>` and `<footer>`. Everything after `<footer>` is prev/next nav junk.
- Heading anchors: empty `<a class="CHHeadingLink" ...></a>` inside every heading — skip them (see the skip-counter pitfall in SKILL.md).
- Mini-TOC sidebars (`class="CHMiniToc_*"`, `class="sidebar"`) may precede or replace body content; extract links but don't mistake the TOC for the body.
- Tables use `class="CHTable"`; code uses `<pre><code>`.
- Title: first `# ` line of extracted markdown; fallback to `<title>` for loose-text pages; placeholder pages may have only `<title>`.

## Performance reference

- Concurrency 8 with retries+linear backoff ≈ 27 pages/s against a live portal.
- ~3,100-topic corpus: full fetch ≈ 2 min; no-change diff run ≈ 3 s (sitemap fetches only).

## CSV contract (proven shape for the downstream AI conversion step)

One row per topic: `publication, slug, url, lastmod, title, content_markdown, outgoing_links, fetched_at`. The CSV is the stable contract; databases/graphs derived from it are rebuildable artifacts. `outgoing_links` (semicolon-joined `/articles/...` hrefs) doubles as the future knowledge-graph edge list — extract it during scraping, it is not recoverable later without re-fetching.
