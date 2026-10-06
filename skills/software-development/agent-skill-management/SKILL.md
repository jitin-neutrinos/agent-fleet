---
name: agent-skill-management
description: Use when installing skills or porting them to OpenCode.
---

# Agent Skill Management

Installing third-party skills (SKILL.md folders) into Hermes (`~/.hermes/skills/<category>/<name>/`) and porting them to the OpenCode docker harness library.

## Preferred install path

1. `hermes skills search <term>` to find the identifier (e.g. `skills-sh/owner/repo/skill-name`).
2. `hermes skills install <id> -y`, then `hermes skills list` to verify (must show `local / enabled`).

## Rate-limit bypass (GitHub API exhausted, no GITHUB_TOKEN)

`hermes skills install` fails with "GitHub API rate limit exhausted (unauthenticated: 60 requests/hour)" on shared IPs. The token in `~/.hermes/.env` may be commented out or dead (test: `curl -H "Authorization: Bearer $T" https://api.github.com/user` → 401 = dead). Bypass:

```bash
mkdir -p ~/scratch/<dir> && cd ~/scratch/<dir>
git clone --depth 1 https://github.com/<owner>/<repo>.git   # git protocol is NOT API-rate-limited
cp -r <repo>/<path-to-skill> ~/.hermes/skills/<category>/<name>
```

Requirements and verification:
- Copied folder MUST contain `SKILL.md` with `name:` frontmatter; Hermes reads the frontmatter name, not the folder name.
- Verify with `hermes skills list | grep <name>` — must show `local ... enabled`.
- Truncated table rows (`dispatching-paralle…`) still count; grep the stem, not the full name.
- Clean the scratch clone afterwards.

## Multi-surface fanout (standard on this machine)

The user wants most skill installs on FOUR surfaces, not just Hermes. OpenCode's canonical path is now `~/.config/opencode/skills/<category>/<name>/` — the old `~/Work/coding-harness/config/skills/` layout was migrated there by the fleet sync (2026-09) and `sync-from-desktop.sh` rsyncs store skills INTO `~/.config/opencode/skills/`, so a manual copy there gets reinforced on every 6-hourly sync:

1. `~/.hermes/skills/<name>/` (skill_manage) or `~/.hermes/skills/<category>/<name>/` (file copy)
2. `~/.claude/skills/<name>/` — Claude Code reads DEPTH-1 ONLY; categories are invisible
3. `~/.gemini/config/skills/<name>/` — agy/antigravity reads FLAT only
4. `~/.config/opencode/skills/<category>/<name>/` — OpenCode globs `**/SKILL.md` recursively

Batch fanout pattern: stage everything in one `~/scratch/<dir>/staging/` tree first,
verify every folder has SKILL.md + `name:` frontmatter, normalize folder names to match
frontmatter names, THEN `cp -r staging/*` into all four targets. Verify each surface with
`find <target> -maxdepth 1 -type d` + SKILL.md existence count, not by trusting cp.

## Verify the whole loop by probing, not by file counts (2026-10-03)

Real failure chain from a 4-surface install: `skill_manage` create landed at TOP-level
`~/.hermes/skills/<name>/` (category is frontmatter, not path — assuming a category path
made the mirror loop `cp: cannot stat`), mirrors were md5-verified as identical, but the
first `~/.tool-router/index --cwd .` run still shipped an index without the new skill.
The loop only counted as done after `~/.tool-router/route "<task phrasing>" | grep -i <name>`
surfaced the skill. Rule: after ANY fanout install, reindex the router and confirm the skill
name appears in the routing card before calling it installed.

## Licence gate before installing into a synced tree

`agent-fleet/sync-from-desktop.sh` (systemd timer, every 6h) mirrors `~/.hermes/skills/`
into the private GitHub repo `jitin-neutrinos/agent-fleet`. Before installing a third-party
skill into `~/.hermes/skills/`, check `license:` frontmatter. Proprietary vendors (e.g.
spotware/ctrader-skills — Spotware EULA) landing there get auto-committed+pushed by the
next sync tick even if the agent asked the user and was still awaiting the answer. Install
locally where the EULA permits, but resolve the fleet-store question in-session — never
leave it to the timer.

## Gotchas

- **Skill name ≠ folder name ≠ repo name.** e.g. `leonxlnx/taste-skill` repo's `taste-skill/` folder has frontmatter `name: design-taste-frontend`. Always check frontmatter.
- **Repos ship provider-specific dist folders.** pbakaus/impeccable ships a ready `.hermes/skills/impeccable/` — prefer it over `skill/SKILL.src.md` (source template). nextlevelbuilder ships `.claude/skills/ui-ux-pro-max/` with its data/scripts.
- **Dedupe first**: some skills may already exist (e.g. obra/superpowers overlaps with Hermes's bundled systematic-debugging / test-driven-development). `hermes skills list` before copying.
- Repo dirs can collide when cloned flat (`emilkowalski/skills` and `anthropics/skills` both → `skills/`). Clone into distinct dir names.
- **Strip a nested `.git` from a standalone-repo skill after copying.** A skill cloned as its own repo leaves a `.git` inside the skills tree; that tree is mirrored into a distribution repo, where the nested repo is recorded as a gitlink — the skill then silently vanishes from every fresh clone and mirror installs delete it from live harness dirs. After copying, `rm -rf <skill>/.git` (full mechanics + fix: `agent-skill-pack-authoring`).

## Porting to OpenCode harness

See references/opencode-harness.md for the kurama-core harness layout and the porting checklist.

## Installed inventory (as of 2026-09-06)

See references/install-registry.md before re-installing anything — it may already be there.