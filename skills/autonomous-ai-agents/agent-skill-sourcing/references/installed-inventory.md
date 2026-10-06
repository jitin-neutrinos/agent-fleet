# Installed Skill Inventory

[verified 2026-09-06] Check/update this before any new sourcing round.

## Hermes (~/.hermes/skills/)

### creative/ (design batch)
- impeccable — pbakaus/impeccable (used repo's own `.hermes/skills/` prebuilt dist)
- design-taste-frontend — leonxlnx/taste-skill (folder `taste-skill`; 'taste')
- emil-design-eng — emilkowalski/skills
- frontend-design — anthropics/skills (official)
- ui-ux-pro-max — nextlevelbuilder/ui-ux-pro-max-skill v2.13

### languages/ (96 skills)
- rust-skills — leonardomso/rust-skills (265 rules)
- rust-best-practices — apollographql/skills
- zig-best-practices — 0xbigboss/claude-code
- golang-* (46) — samber/cc-skills-golang
- elixir-* etc (47) — igmarin/elixir-phoenix-skills

### software-development/
- superpowers set added: brainstorming, writing-plans, executing-plans, dispatching-parallel-agents, subagent-driven-development, using-superpowers, using-git-worktrees, writing-skills, finishing-a-development-branch, receiving-code-review — obra/superpowers
- system-design, architecture — anthropics/knowledge-work-plugins (engineering/skills/)
- already-present dupes skipped: systematic-debugging, test-driven-development, verification-before-completion, requesting-code-review

## OpenCode (~/Work/coding-harness/config/skills/)

2026-09-17: + brag — latent-spaces/brag (skills-sh/latent-spaces/brag/brag). Launch-video skill; root of library, INDEX.md line added. Also installed: Hermes media/, ~/.claude/skills/ (claude -p probe confirmed 2026-09-17). Prereqs present: node 22.22, ffmpeg 8.1.

Host-side since 2026-09-07 (opencode runs on host, config at ~/.config/opencode/opencode.json). Skills library at ~/Work/coding-harness/config/skills/ symlinked into workspaces as `.skill-library`. Design: only project skills + whitelisted names appear in the visible skill list; the rest are read on demand via INDEX.md grep (context discipline for local 9B models — do NOT whitelist the whole library).

2026-09-07 enrichment round:
- +30 database/analytics skills to languages/ (supabase*, sql-optimization, postgresql-table-design, database-migration, mongodb-*, redis-core, duckdb*, prisma-*, neon*, pandas, xlsx, scikit-learn, statsmodels, matplotlib, critical-code-reviewer, data-storytelling, kpi-dashboard-design, quarto-authoring, exploratory-data-analysis, data-quality-frameworks). INDEX.md deduped (222 entries).
- MCPs added: sequentialthinking (@modelcontextprotocol/server-sequential-thinking), playwright (@playwright/mcp). Verified via live run.
- Plugin added: ~/.config/opencode/plugins/notify.ts — native notify-send notifications on session.idle/error/permission.updated.
- Evaluated + rejected: oh-my-opencode (multi-agent orchestration assumes frontier cloud models; drowns a 9B context), filesystem/fetch MCPs (built-in), safety-net (permission config already blocks rm -rf/sudo).

## Sourcing research shortlist (database/analytics, not yet installed as of 2026-09-06)

Recommended set if user proceeds:
- supabase-postgres-best-practices + supabase — supabase/agent-skills (388K installs)
- sql-optimization-patterns, postgresql-table-design, database-migration — wshobson/agents (2.0M total)
- prisma suite (5) — prisma/skills
- mongodb-schema-design/-query-optimizer/-connection — mongodb/agent-skills (official)
- redis-core — redis/agent-skills (official)
- duckdb-query — duckdb
- posit-dev/skills: critical-code-reviewer, tidyverse, quarto (data science, 492★)
- data-storytelling, kpi-dashboard-design — wshobson/agents
- pandas-data-analysis — midudev/autoskills
- xlsx — anthropics/skills
Skip unless platform adopted: neon, planetscale, turso, convex, firebase.
