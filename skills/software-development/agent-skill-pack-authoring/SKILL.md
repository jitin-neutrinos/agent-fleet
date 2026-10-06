---
name: agent-skill-pack-authoring
description: "Use when building or auditing a multi-skill agent pack."
created_by: agent
---

# Agent skill-pack authoring

Class: building a *pack* of related skills (one core skill + N media/domain
skills sharing its assets) so it is spec-conformant, portable across harnesses,
and installable repeatably — spec conformance, asset indexing, installer,
validator, tests. Single-skill authoring is `hermes-agent-skill-authoring` /
`writing-skills`; this covers the pack-level engineering around them.

## Spec floor (agentskills.io)

- Frontmatter: `name` (regex `^[a-z0-9]+(-[a-z0-9]+)*$`, must equal the parent
  directory name), `description` (1-1024 chars). Optional portable fields:
  `license`, `compatibility`, `metadata` (string→string map), `allowed-tools`.
- `version` is NOT a spec field — put it in `metadata.version`.
- Claude Code accepts a large superset (`when_to_use`, `model`, `hooks`,
  `argument-hint`, …). A portable pack ships none of it.
- Paths resolve relative to the skill root. Never emit harness variables
  (`${CLAUDE_PLUGIN_ROOT}` etc.) or a `skills/` install-prefix in pack docs.

## Path contract (the #1 pack defect)

Cross-skill asset references break between install layouts. Fix once, in the
core skill: all pack skills are always siblings, so cross-skill paths are
`../<core-skill>/assets/...`; within a skill they are relative to that skill's
root. State the contract in the core SKILL.md and reference it everywhere;
never use a plugin-root-relative prefix — it only resolves in plugin installs.

## Asset usability rules

- **Opaque asset IDs are unusable by agents.** An icon library named by asset
  ID forces dozens of image reads to pick one. Ship an index mapping
  concept/tags → per-variant filename, checked in as data, and write the
  selection instructions as "read the index, match the concept" — never
  "preview the folder".
- **Do not assume variant folders are slot-aligned.** Same icon count ≠ same
  order. Verify by exact alpha-silhouette match (ImageMagick `-alpha extract`
  → RMSE; 0.0 = identical shape) before deriving any ordinal mapping, and
  record per-folder filenames in the index rather than a single slot number.
  Keep the index generator as a tool so labels stay regenerable.
- **A multi-artwork SVG sheet is not a placeable asset.** Before documenting
  "use the bundled SVG", check its structure (viewBox, groups, path count).
  An Illustrator artboard needs splitting into per-artwork SVGs first; name a
  specific file in the docs, and mark the sheet as reference-only.
- Verify visual claims by rasterizing (inkscape → montage) and checking pixel
  histograms, not by eyeballing a montage — white art on a white background
  reads as "missing" to a vision pass.
- Keep every hex value in sync between the CSS and JSON token files; a color
  used in prose/CSS but absent from the machine-readable tokens is drift.

## Script hardening (host hygiene)

- A bundled script must never `pip install` into the system interpreter.
  Pattern: use an importable package if present; else behind an explicit
  `--allow-install` flag create a dedicated venv (`uv venv` preferred) and
  `os.execv` re-exec; else print exact manual instructions and exit non-zero.
- Scripts resolve their own inputs from `__file__`, take explicit override
  flags, and make no cwd assumptions.
- One self-check script (stdlib + the render dependency only) proves the
  pipeline end-to-end on a clean machine.

## Installer

- **Do NOT delegate Tier-1 placement to the `skills` CLI.** Verified against the real CLI:
  it silently ignores `-a` agent scoping for local-path installs and creates skill folders
  for every agent it knows (~50 empty `.<agent>/skills` dirs in the user's home per run) —
  the source of phantom-harness litter. Know the targets (discovery, below) and place the
  skills yourself with plain `shutil.copytree` into exactly those targets; use the CLI only
  for what nothing else covers (Claude plugin/marketplace registration). Cover the CLI's
  remaining gaps: rules-file downgrade artifacts, reconciliation of pre-existing hand
  copies, and post-install verification.
- **Discover harnesses device-wide, by evidence.** A fixed list of well-known home dirs
  misses project-scoped harnesses (a `.claude` inside a repo, a `.gemini` inside a tool
  folder). Walk every accessible root (home first, then `/opt`, `/srv`, `/mnt`, `/media`,
  `/workspace`, `/root` — never other users' homes) looking for each harness's marker
  directory, and count a find only when real evidence exists: the harness binary on PATH,
  config/state files inside the marker, or foreign (non-ours) skill content. Prune descent
  into caches, dependency trees, and other harnesses' internal machinery (sandboxes,
  profiles, plugin caches, session stores) — they mirror home layouts and generate noise.
  Cap depth and directory count so a pathological tree cannot hang the scan.
- Evidence rules that matter:
  - Binary-only proof (marker dir absent, binary on PATH) counts only at the *home root*,
    and only for the invoking user — a bare `.claude` in a random project is not a project
    harness. Honour `$HOME` here so sandboxed runs treat the sandbox as home.
  - A marker dir whose only contents are the pack's own skill names is a phantom — skip.
  - Project-scope markers need content beyond a skills folder (config, state, foreign
    skills) to count.
  - **An empty scan result is a real answer.** Falling back to the well-known list on
    empty reinstalls into folders that may not exist; report "nothing to attach to".
  - A discovery-verified harness without a skills dir yet (binary-only evidence) gets one
    created at install time — safe precisely because discovery vetted the parent.
- Verify = from each install location, resolve a known cross-skill asset path
  and assert it exists. This is the check that catches broken path contracts.
- First run defaults to dry-run; refuse to install over unreconciled
  duplicates; record created paths in a state file and never delete paths the
  installer did not create; back up any config file before editing.
- Uninstall must also cover registered state a directory sweep cannot reach (Claude plugin
  + marketplace registration), and its per-harness success test inverts: a harness no
  longer carrying the pack is the DESIRED result — judging by presence labels a clean
  removal FAILED.

### Installer details that bite (measured, not theoretical)
- **Record every installed path, symlink AND real copy.** The `skills` CLI links
  harness dirs to one real copy in its own store (`~/.agents/skills`). Recording
  only the symlinks leaves the store unrecorded, so duplicate detection counts it
  as a foreign conflict — every re-install then refuses with DUPLICATES FOUND, and
  uninstall cannot clean it up. Exclude state-recorded paths from duplicate
  detection and prefer the store when naming a "canonical" location.
- **Tier-2 (rules-file) generation** is a real transform, not a copy: flatten
  SKILL.md + `references/*.md` into one file, and rewrite relative references to
  absolute paths into the canonical install — a Tier-2 harness reads one file and
  cannot follow a link. Handle both `../<sibling-skill>/...` and same-skill
  `../assets/...` forms. `AGENTS.md` gets a **catalog** (name, description, section
  map) rather than the flatten: a 7-skill pack flattens to ~60k chars, against an
  8k cap. Caps are hard — refuse the target loudly and exit non-zero instead of
  truncating a brand guide.
- The store copy means repo edits do **not** reach installed harnesses until a
  re-install; say so when reporting, or the user will edit a skill and see no change.
- **Detect a harness by real evidence, never by directory existence.** The installer (or
  a debug run of the `skills` CLI) CREATES harness directories as a side effect, so the
  next run's folder-probe "detects" a harness the user does not have and installs into
  the phantom. Probe for the tool's binary, config file, or pre-existing skill content;
  exclude the pack's own recorded paths from the probe. Before trusting any per-harness
  path, verify it against the user's live machine (where does an existing skill actually
  sit?) — the assumed path can be wrong outright (e.g. opencode reads
  `~/.config/opencode/skills`, not `~/.opencode/skills`).
- **Idempotency is byte-diffable**: a second install must leave the tree identical. A
  fresh timestamped `.bak` per run accumulates forever — keep ONE rolling `.bak` written
  only when content actually changes, and route config writes through a
  write-if-changed helper so no-op runs change nothing.

### Hosting the installer publicly (mirrors a working MCP setup)
- Pattern: build a versioned `pack-<version>.tar.gz` + `SHA256SUMS`, serve them from a
  throwaway static server (`python3 -m http.server <port> --bind 127.0.0.1`, systemd user
  unit) and expose it through an existing cloudflared tunnel with a two-line ingress rule
  in `~/.cloudflared/config.yml`. DNS is one command —
  `cloudflared tunnel route dns <tunnel> <hostname>` — no dashboard visit needed. Point the
  deploy script at the served URL and re-fetch every file to compare byte-for-byte.
- The installer must **verify a published SHA-256 before extracting**, and validate archive
  members (no absolute paths, no `..`, no escaping symlinks). Extract to a private temp dir,
  clean up in `finally`.
- `curl | bash` installers cannot rely on `$HOME` faking for tests, and the bootstrap must
  forward flags (`... | python3 - "$@"`) so `bash -s -- --remove` works.
- **Check connector count before blaming the ingress**: two enabled systemd units can run
  the SAME tunnel, Cloudflare load-balances between them, and a hostname added to only one
  config 404s on about half of requests. `pgrep -cf 'cloudflared tunnel'` must be 1.
- In a `set -euo pipefail` script, `producer | grep -q pattern` reports FAILURE when the
  pattern is found — grep exits at the first match, the producer takes SIGPIPE. Write the
  output to a file and grep the file.
- **Never publish different bytes under the same filename through a CDN.** Default edge
  caching keeps the first archive (hours) while the checksum manifest stays fresh, so
  every client downloads one version's bytes against another version's hash and the
  installer's checksum gate refuses everything. Fix all three legs: content-addressed
  filenames (short content hash in the name, so a cached name can never go stale), a
  deterministic build (fixed mtimes/names in the tarball — same tree, same hash), and
  explicit `Cache-Control` headers (`max-age=31536000, immutable` for content-addressed
  files, `no-store` for the manifest and bootstrap scripts). `python3 -m http.server`
  sends no cache headers — serve through a small custom handler or the CDN's defaults
  apply.
- **The TUI must read the archive name from the published manifest, not hardcode it** —
  a hardcoded name breaks the moment content-addressing changes the filename, and a
  retry-once on download failure covers a publish landing mid-download.
- **TUI animation is TTY-only**: gate repaint/ramp effects on `isatty`, offer `--no-anim`,
  and always restore the cursor. Test under a real pty (`pty.openpty`) by grepping raw
  output for the ramp glyphs; assert the piped run has none.
- **Count one thing everywhere in the TUI.** Detection, "Installing into N", and the
  final summary must all count harness TYPES (unique labels), not install locations —
  multi-location harnesses make a per-location count disagree with the list above it
  and the user reads that as data corruption. Show per-location detail only as a
  `(N locations)` suffix on the type's row.
- **Separate detection from write targets, visibly.** Discovery legitimately finds
  project-scope harness state (a tracked `.cursor` dir in a client repo) that install
  must not touch by default. Display it in its own collapsed group ("also found in
  project folders — not installed system-wide, skipped") instead of the detected list:
  a project config folder reads to the user as "I have Cursor installed" when it isn't.
  Default installs to user scope with project scope opt-in; let uninstall/verify still
  see project scope so they can clean what an older run wrote.
- **Verify TUI animation through a terminal emulator, not the raw byte stream.** A raw
  pty capture shows every intermediate frame (dim lines, pre-repaint checklist rows)
  and looks corrupted when it isn't; feed the bytes through `pyte` (pip install pyte)
  and assert on `screen.display`. Raw-grep only for negative checks (piped run has no
  ramp glyphs, no cursor escapes).
- **Re-export `HOME` before any deploy/build step in a persistent terminal session.**
  Sandbox tests that `export HOME=<sandbox>` (or `cd` into a sandbox) leak into later
  tool calls — a deploy script deriving paths from `$HOME` then publishes into a scratch
  tree instead of the real web root. Verify `$HOME` and cwd at the top of any step that
  writes outside the sandbox.

## Auditing a live distribution

When asked "where do we stand" on a distributed pack, verify each leg with real
output — the plan doc and earlier session summaries are context, not evidence. Four
legs: repo fidelity (fresh-clone SKILL.md count == working tree, visibility), mirror
run (trigger the sync unit once instead of waiting for its timer), hosted installer
(served file hash == repo == web-root copy), runtime clone (pull it, re-count).
Command-level recipe: `references/distribution-repo-audit.md`.

## Validator (CI gate)

One stdlib script, run on every push: spec conformance (fields, name regex,
name==dir, no harness-only keys, description budget), link/asset integrity
(every path and bundled filename mentioned in prose resolves), token budget,
token consistency (every hex in prose exists in tokens.json), portability (no
harness variables, no install-prefix paths, no machine-specific paths), and
file-mode sanity. Note: `claude plugin validate` checks manifests only and
never opens SKILL.md files — it is not a substitute.

## Validator heuristics that avoid false positives

- Backtick tokens are prose as often as paths: skip `...` ellipses, CSS class
  tokens (`.foo`), CSS values (`-0.01em`), URLs, and absolute paths.
- Bare filenames (`foo.png`, `font.ttf`) resolve against a base-list (skill
  root, its subdirs, sibling core skill's assets subdirs, repo `tools/`) —
  include binary extensions, not just code/doc extensions.
- A "never use X" instruction that quotes X is compliant; check surrounding
  context lines before failing on a forbidden-pattern match.

## Test suite shape

Assert-based stdlib runner (`tests/test_all.py`, no frameworks): spec checks
per skill, path-contract greps, index integrity (every indexed file exists,
mapping is injective and fully covers each folder), splitter/manifest output
counts, validator passes, and installer behavior against a sandbox `$HOME`
(planted stale copy → doctor flags it; install defaults to dry-run; copy-mode
fallback lands files; verify passes; second install is a no-op; uninstall
removes only state-recorded paths). Keep test string-matches narrow — matching
help-text prose creates false failures when wording changes.

### Sandboxing a test: `$HOME` is not enough
A faked `$HOME` does **not** isolate environment-dependent tools from the real machine.
Two measured traps:
- A faked `$HOME` does not isolate the `skills` CLI — it resolves harness paths from the
  passwd home (`os.userInfo()`), so a "sandboxed" test that takes the CLI branch writes
  symlinks into the user's LIVE skill directories while its sandbox stays empty. Force the
  copy path instead, and hide `npx` correctly: `npx` can live in `/usr/bin`, so
  `PATH=/usr/bin:/bin` does not hide it — point `PATH` at an empty directory containing
  only the interpreter and shell basics. (A PATH that still exposes real harness binaries
  breaks tests that assert a harness-less machine: binary-on-PATH is detection evidence.)
- When a test needs to simulate "binary exists but no marker dir", set `$HOME` to the
  sandbox via `os.environ` in-process (not just a subprocess env) — evidence rules key off
  the home root, and only the `$HOME` env var makes the sandbox count as home.

### A verify that checks zero locations must fail
An installer that lands nothing used to print "0 install locations checked" plus
"verify PASS" and exit 0 — a false green on a completely broken install. Fail
when the checked count is 0, and leave a regression test asserting a no-op
install exits non-zero.

### Test an uninstaller against real state, not just the happy path
Cover with assertions: removal is reported as success (not failure), removal actually
removes the skills and the Tier-2 rules files it wrote, the state record is cleared, and
a second uninstall is a clean no-op. Match installed paths narrowly — counting every
path containing the pack name counts the installer's own state file and reports false
leftovers.

## Pack-level pitfalls

- A skill existing only in a runtime directory (`~/.hermes/skills/...`) with
  absolute paths baked in is untracked work — adopt it into the repo,
  de-pathed, before anything touches that directory.
- Partial hand-copies of a pack in multiple harness skill dirs cause duplicate
  skill registration and silent drift; detect, report, and reconcile them
  (doctor command) rather than installing over them.
- Live config pointing at a moving/deletable location (e.g. a marketplace
  pinned to `~/Downloads`) dangles silently; re-point to the durable repo
  path or a git remote.
- Deletion of anything outside the repo (hand-copies, config edits, remote
  push) requires explicit user confirmation — batch these into one
  plain-English confirmation gate rather than asking inline mid-work.
- **A skill dir that is itself a git checkout breaks the distribution repo.** A skill
  installed standalone from a registry carries its own `.git`; committing the pack then
  records a mode-160000 **gitlink** for that path — no `.gitmodules` needed — and tracks
  none of its file content (the gitlink persists even after the nested `.git` is later
  deleted, until flattened). Symptoms: `git status`/`git check-ignore` says "is in
  submodule <path>", `git ls-files -s <path>` shows `160000`, and a fresh `git clone`
  yields an EMPTY dir — one SKILL.md short of the working tree. Worse: the clone is what
  a mirror-mode installer installs from, and `rsync -a --delete` then DELETES that skill
  from every live harness dir on the next run. Fix by flattening — `git rm --cached
  <path>`, delete the nested `.git`, `git add <path>`, commit — and add `--exclude=.git`
  to the skills rsync in the sync script so it cannot reappear. Verify by cloning into a
  scratch dir and matching `find <clone>/skills -name SKILL.md | wc -l` against the
  working tree.
- **The one-liner's clone-once runtime copy goes stale after repo-level fixes.** An
  installer that reuses `~/<pack>` when present keeps executing the old tree until
  something pulls it; after pushing a fix, `git pull --ff-only` the runtime clone and
  re-check its content, and confirm the fix again from a fresh scratch clone.
- **A whole-tree secret scan trips on the pack's own fixtures.** Redaction-test fixtures
  and reference docs legitimately contain key-shaped strings. Scope the mirror's secret
  gate to newly changed paths, and when a hit appears, list the file
  (`git grep -lI <pattern>`) and read the matched line before calling it a leak —
  placeholders like `ghp_xx...xxxx` / `AKIAIO...MPLE` are documentation.