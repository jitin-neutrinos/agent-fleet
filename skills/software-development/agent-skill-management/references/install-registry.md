# Install registry (what is already installed)

Check here before installing or re-cloning. Unless noted, skills land in four surfaces:
`~/.hermes/skills/languages/`, `~/.claude/skills/`, `~/.gemini/config/skills/` (agy),
`~/Work/coding-harness/config/skills/languages/` (+ INDEX.md entry).

## Batches installed

| Batch | Source repos | Count | Surface counts verified |
|---|---|---|---|
| Design | pbakaus/impeccable, leonxlnx/taste-skill, emilkowalski/skills, anthropics/skills, nextlevelbuilder, anthropics/knowledge-work-plugins, obra/superpowers | 16 | hermes 17 enabled |
| Languages (rust/go/elixir/zig) | leonardomso/rust-skills, apollographql/skills, 0xbigboss/claude-code, samber/cc-skills-golang (46), igmarin/elixir-phoenix-skills (47) | 96 | hermes/opencode 96, claude 37, agy 36 |
| Databases & analytics | supabase/agent-skills, prisma/skills, mongodb/agent-skills, redis/agent-skills, neondatabase/agent-skills, duckdb (official+silvainfm), wshobson/agents, posit-dev/skills, midudev/autoskills, anthropics/skills xlsx | 27 | hermes 123, claude 37, agy 36, opencode 123 |
| Python/AI-ML/automation/debug/security | wshobson/agents (python suite, security set), sickn33/antigravity-awesome-skills, K-Dense-AI/scientific-agent-skills (ML subset), mattpocock/skills diagnosing-bugs, arm64be/codex-things kde-computer-use | 56 | hermes/opencode 179, claude 93, agy 92 |
| Local AI / SLM / content-gen | av/skills run-llms, hermes official mlops (llama-cpp, vllm, unsloth, axolotl, trl, flash-attention, whisper, stable-diffusion, chroma, qdrant), aka-kika local-ai-ollama, official creative comfyui | 13 | hermes/opencode 192, claude 106, agy 105 |

## Deliberately skipped (do not re-suggest)

- `pull-llamacpp-model` (av/skills) — hardcoded AMD ROCm toolbox image, wrong for NVIDIA hosts.
- `distributed-debugging` (wshobson) — agents/commands plugin, no SKILL.md.
- neon/planetscale/turso/convex/firebase vendor suites beyond core picks — platform-locked.
- clawhub `administering-linux`-style one-offs — thin wrappers.

## Registry search identifiers that worked

- `hermes skills search <term>` → Skills Hub table; identifiers look like `skills-sh/<owner>/<repo>/<skill>`.
- Ambiguous names resolve via full identifier; multiple repos share names (e.g. three `system-design`).
- GitHub raw check of SKILL.md frontmatter (`curl -s https://raw.githubusercontent.com/<owner>/<repo>/main/<path>/SKILL.md | head`) settles name mismatches before cloning.

## Known gaps

- `hermes skills install` needs GITHUB_TOKEN for rate limits; token in `~/.hermes/.env` was commented out and dead (401) as of 2026-09-06. Git clone bypass is the reliable path.