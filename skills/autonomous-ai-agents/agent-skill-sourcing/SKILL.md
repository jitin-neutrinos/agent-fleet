---
name: agent-skill-sourcing
description: "Find and install agent skills from registries for a topic."
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [skills, installation, skills-sh, opencode, hermes]
    related_skills: [hermes-agent-skill-authoring]
---

# Agent Skill Sourcing

Find the best existing agent skill for a capability, install it into Hermes, and port it to the Claude Code and OpenCode harnesses. User runs this workflow repeatedly (design, languages, database/analytics so far) and expects both surfaces updated in one pass.

## When to Use

- User asks to "research and install" / "find the best" skills for a topic
- User names skills vaguely ("taste", "super powers", "ui ux pro max") — resolve to real registry entries, never guess
- Don't use for: authoring new skills (use hermes-agent-skill-authoring)

## Procedure

1. **Resolve identifiers.** `terminal("hermes skills search <topic>")` (paginated tables — grep them, they truncate names) plus a web search of skills.sh. Registry searches return similarly-named near-misses (brag vs brag-doc vs BotBrag) — pick by description match with the request and say which near-misses you skipped and why. Check GitHub repo contents when a skill name is ambiguous: the repo folder and the SKILL.md `name:` frontmatter often differ (e.g. leonxlnx/taste-skill repo folder `taste-skill` → skill `design-taste-frontend`). Install by the identifier Hermes reports, verify by the frontmatter name.
2. **Evaluate before recommending.** Install counts (1K+ floor, prefer 100K+), source reputation (official vendor repos > unknown authors), recency. When the request already authorizes install ("find and install X"), skip the recommendation gate and install; present the findings table with the completion report instead of waiting for approval.
3. **Dedupe check first.** `hermes skills list` before installing. Whole suites arrive with overlaps (e.g. obra/superpowers vs existing systematic-debugging, TDD, verification-before-completion) — skip existing dupes and say so.
4. **Install to Hermes.**
   - Try `hermes skills install <identifier> -y` first.
   - **Rate-limit fallback (the common path):** unauthenticated GitHub API is 60 req/hr and usually exhausted. The commented `GITHUB_TOKEN` in `~/.hermes/.env` may be dead (401). Bypass: `git clone --depth 1` each source repo into `~/scratch/<name>/` (git protocol is not API-rate-limited), then `cp -r <skill-dir> ~/.hermes/skills/<category>/<name>/`.
   - Skill dir must contain SKILL.md with `name:` frontmatter or it won't load.
   - The same API rate limit stalls `hermes skills inspect` — it can hang past the terminal timeout. When install is rate-limited, skip inspect entirely: clone and read the repo's SKILL.md/README directly.
   - Probe the skill's stated prerequisites (node version, ffmpeg, etc.) against the host in the same call batch as the clone; prefer a skill whose prereqs are already met over one needing new system packages.
   - Some repos ship pre-built Hermes distributions (e.g. pbakaus/impeccable has `.hermes/skills/`) — prefer those.
5. **Verify.** Hermes: `hermes skills list | grep <category>` — every installed skill must show `local ... enabled`; count against what was requested. Harness installs: verify with the harness's own probe (`claude -p 'reply with only your skills matching X'`), never file counts.
6. **Port to the other harnesses.**
   - Claude Code: `cp -r <skill-dir> ~/.claude/skills/<name>/` — it scans only depth-1 under skills/, so no nesting.
   - OpenCode is HOST-side: skills live at `~/Work/coding-harness/config/skills/` (symlinked into workspaces as `.skill-library`). The library root is flat — if no category dir matches, copy to the root. Copy dirs, then append one INDEX.md line per skill (`- **name** — short description`) under the matching section — not a bare list. If adding to a category dir like `languages/`, mirror the Hermes category exactly (`ls ~/.hermes/skills/<category>/ | wc -l` must equal the OpenCode count).
   - Match the Hermes category by what the skill DOES, not its name — a skill that produces videos is media/ whatever it's called.
7. **Dedupe INDEX.md after appending.** Script it: parse `- **name**` lines, keep the FIRST occurrence, drop repeats — re-running this workflow reliably double-appends because the check for existing entries is grep-based and stale after category-wide copies. Then verify index entry count against `find config/skills -mindepth 2 -name SKILL.md | wc -l`.
8. **Log + clean.** Append the round to `references/installed-inventory.md` (skill, source, surfaces, category), then remove the clone dirs.

## Pitfalls

- **Truncated table names:** hermes skills search renders narrow boxes — extract full identifiers with grep on the identifier column, or install will fail with 'could not find'.
- **Suite bloat:** don't install all 38-47 skills of a mega-repo blindly; user approved full suites for languages, but for one-off topics pick the 2-5 relevant ones.
- **INDEX.md descriptions:** skills with multi-line YAML descriptions produce `— >` garbage lines when naively regex-extracted; sanitize broken entries after appending.
- **Existing category folders** in `~/.hermes/skills/`: creative, languages, software-development, autonomous-ai-agents, etc. Match new skills to the right one.
- **INDEX.md grep-check before appending** matches by `- **name**` and old entries may sit under different section headings — always count occurrences after the append; anything at 2 is a dupe to remove (keep the first).
- **Verify port by copying what exists, not by re-sourcing:** for a port-only round (skill already in Hermes), read the inventory reference first, copy the dirs with a script, and skip the whole clone/install phase.
- **skill_manage patch semantics:** pass `old_string`/`new_string` only — combining `content` with `old_string` is rejected. In a patch that inserts a section before an existing heading, include the full heading line in both old_string and new_string, then re-read the file: an over-eager match can swallow the next section's heading (happened with '## Hard Invariants' in hermes-agent).

## Verification

Hermes: grep of `hermes skills list` shows each new skill `local/enabled`. Claude Code: a live probe lists the skill. OpenCode: every new dir has SKILL.md and an INDEX.md line. Report counts for every surface touched plus any dupes skipped.

## References

- `references/installed-inventory.md` — what is already installed on both surfaces, sources, and category layout. Check before any new install round.