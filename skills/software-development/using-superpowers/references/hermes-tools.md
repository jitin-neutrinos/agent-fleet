# Hermes Agent Tool Mapping

Skills speak in actions ("dispatch a subagent", "create a todo", "read a file"). On Hermes Agent these resolve to the tools below.

## Tools

| Action skills request | Hermes tool |
|---|---|
| Read a file | `read_file` |
| Create a new file | `write_file` |
| Edit a file (targeted patch) | `patch` |
| Run a shell command | `terminal` |
| Search file contents | `search_files` |
| Find files by name | `terminal` with `find` |
| Fetch a URL / read a webpage | `web_extract(urls=[...])` |
| Search the web | `web_search(query=...)` |
| Dispatch a subagent | `delegate_task(goal=..., context=..., toolsets=[...], role="leaf")` |
| Task tracking | `todo` tool |
| Invoke a skill | `skill_view("skill-name")` |

## `search_files` globs match the basename only — `**/` silently returns zero

Proven 2026-10-05 on `~/.hermes/skills` (Hermes build of that date). Both the
content-mode `file_glob` filter and the `target="files"` pattern are matched
against the file's **basename**, never against a path segment. A leading `**/`
therefore matches nothing and the call returns `total_count: 0` with no error —
which reads exactly like "the file does not exist".

| Call on `~/.hermes/skills` | Result |
|---|---|
| `file_glob="**/SKILL.md"`, pattern `taal` | `total_count: 0` |
| `file_glob="SKILL.md"`, pattern `taal` | `total_count: 2` |
| `file_glob="**/*.md"` in `dev/`, one known literal | `total_count: 0` |
| `file_glob="*.md"` in `dev/`, same literal | `total_count: 1` |
| `target="files"`, pattern `*strangler*` | `total_count: 0` |
| `target="files"`, pattern `local-edge-model-service.md` | `total_count: 1` |

Write the basename glob — `SKILL.md`, `*.md`, `*model-service.md`. A
directory name is NOT part of the match, so `*strangler*` finds nothing even
though `strangler-fig-rust-port/` is full of files. Narrow with `path=` to
reach a subtree instead of reaching for `**/`. Never trust a `0` from a `**/`
glob as evidence of absence — re-run with a bare basename before concluding
anything.

`target="files"` discovery is also bounded: results came back
`truncated: true, total_count_is_lower_bound: true`, so its `total_count` is a
floor, not a census. Use `offset=` to page.

## Content search does NOT descend into dot-directories

Proven 2026-10-04 on a fixture HOME (`wt-fleet/fake-home`) whose rulebooks and
skills all live under `.claude/`, `.gemini/`, `.hermes/`. Same `path=`, same
call — only the file's location differs:

| `search_files(pattern=…, path=fake-home)` | Result |
|---|---|
| `Neutrinos Designer` (in `fake-home/AGENTS.md`) | `total_count: 1` |
| `astra-canvas:start` (in `fake-home/.claude/CLAUDE.md`) | `total_count: 0` |
| `export\.arxiv\.org/api/query` (only in `fake-home/.hermes/skills/research/arxiv/SKILL.md`) | `total_count: 0` |
| the same arxiv literal, `path=fake-home/.hermes/skills/research` | `total_count: 1` |

A `0` therefore means "not visible from this path", not "absent" — and a
`fake-home`-shaped tree is exactly where a false absence hurts, because
`~/.claude`, `~/.gemini` and `~/.hermes` are all dot-dirs. Point `path=` AT the
dot-dir (or a subdir of it) when hunting for rulebook markers, skill markers or
SOUL sections; otherwise confirm with `terminal` `grep -rln` before concluding a
file or marker is missing. Never treat one `0` as a census.

## Instructions file

When a skill mentions "your instructions file," on Hermes Agent this is **`AGENTS.md`** in the project directory, or **`SOUL.md`** globally at `~/.hermes/SOUL.md`.

## Invoking a skill

Hermes Agent has a `skills` toolset with `skill_view` and `skills_list` tools.
To invoke a superpowers skill, use:

```
skill_view("brainstorming")
skill_view("test-driven-development")
```

If `skill_view` cannot find a superpowers skill (it may not appear in the catalog
until the plugin fully registers it), fall back to reading the SKILL.md directly:

```
read_file(path="~/.hermes/plugins/superpowers/skills/<skill-name>/SKILL.md")
```

This fallback is the same mechanism used by other harnesses without native skill loading.

## Subagent dispatch

Use `delegate_task` to spawn isolated subagents for parallel or sequential workstreams:

```
delegate_task(goal="...", context="...", toolsets=[...], role="leaf")
```

If `delegate_task` is unavailable, do the work inline rather than inventing tool calls.

## Task tracking

Use the `todo` tool for task tracking within a session. For multi-agent task boards, use `hermes kanban` CLI if available. Treat older `TodoWrite` references as the task-tracking action.
