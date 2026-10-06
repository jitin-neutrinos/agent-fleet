# Candidate landscape for shared agent memory

Survey of the options, the evidence behind the pick, and why the rest were rejected. Checked
before recommending anything so the same ground is not re-covered.

## Where memory actually lives today (kurama-core, verified locally)

| Implementation | Store | Reachable by others? |
|---|---|---|
| Hermes default profile | `~/.hermes/memories/` + `~/.hermes/memory_store.db` (holographic provider) | no |
| Hermes profiles (coder, ops, desktop, researcher, reviewer) | `~/.hermes/profiles/<p>/memories/` | no — isolation is by design |
| Hermes subagents / cron | inherit the profile store | no |
| Claude Code | `~/.claude/` + CLAUDE.md files | no |
| OpenCode / agy / Codex | their own harness stores | no |

`hermes memory --help` lists the bundled external providers: honcho, openviking, mem0, hindsight,
holographic, retaindb, byterover. **Only one external provider can be active at a time**, and all
of them are Hermes-internal — none of them reaches the non-Hermes CLIs. Built-in
`MEMORY.md`/`USER.md` is always active alongside.

## Candidates

| Candidate | Storage / deps | Cross-tool reach | Recall | Verdict |
|---|---|---|---|---|
| **agentmemory** (rohitg00, Apache-2.0) | SQLite + `iii` engine; advertises "0 external DBs" | Named support incl. Hermes, OpenCode, Claude Code, Codex CLI, Gemini CLI; 54 MCP tools, 12 auto hooks | BM25 + vector + knowledge graph with RRF; local free embeddings | **Recommended pick** |
| **engram** (Gentleman-Programming, MIT) | One Go binary, SQLite + FTS5, no runtime deps | Any MCP client; `engram setup <agent>` writers; git-chunk sync between machines | FTS5 keyword only by default | Runner-up — wins on deps, loses on accuracy |
| Zep / Graphiti | Needs FalkorDB or Neo4j (+ model + embedder per ingestion) | Via MCP | Best temporal reasoning (validity windows) | Rejected: container + per-write model cost |
| Mem0 / OpenMemory | Docker + Qdrant + OpenAI key | Via MCP | Mem0 v1 weak on temporal in independent re-tests | Rejected: OpenMemory carries a vendor sunset notice |
| claude-mem | TypeScript + Python + ChromaDB worker | Claude Code only | — | Rejected: per-tool, defeats the purpose |
| Hermes bundled providers | Hermes-internal | Hermes only | Good (self-reported) | Keep as-is; cannot serve other CLIs |
| Mastra Observational Memory | TypeScript library inside Mastra | No server surface | Benchmark-leading | Steal the design (compression, append-only log), cannot adopt as a service |

## Benchmark evidence (and how to read it)

LongMemEval (ICLR 2025) is the closest thing to a fair multi-session memory comparison:
~115k-token histories across ~40 sessions, testing cross-session recall, knowledge updates,
temporal reasoning, abstention.

| System | Reported | Note |
|---|---|---|
| Mastra Observational Memory | 94.87% (gpt-5-mini), 84.23% (gpt-4o) | Highest openly reproducible; reported to beat the oracle ceiling |
| agentmemory | 95.2% R@5 retrieval, ~92% fewer tokens | Local embeddings, offline |
| Zep / Graphiti | ~71% overall, 63.8% temporal subtask | Temporal knowledge graph |
| Mem0 v1 | 49.0% temporal (independent re-test) | Vendor self-reports much higher after a rewrite |
| Naive full-context | 60–64% | The floor to beat |

Read every row with its runner. Independent re-tests and vendor self-reports diverge by 40+
points on the same framework, and large-context models make these benchmarks borderline
saturated — which is why the decision rests on the requirement decomposition and integration
fit, not on the leaderboard.

## Rejections and why (with sources)

| Rejected | Reason |
|---|---|
| mem0 OpenMemory | Vendor sunset notice on its own README; needs Docker + Qdrant + an OpenAI key |
| Zep / Graphiti | Requires FalkorDB or Neo4j plus a model and embedder per ingestion step |
| claude-mem | Single-vendor reach — no cross-tool value |
| plain-Markdown memory (Obsidian-style) | Lovely to hand-edit, no temporal model or hybrid recall |
| Swapping the Hermes bundled provider | Providers are Hermes-internal; solves nothing for the other CLIs |
| A bespoke MCP memory server | Reinvents hybrid ranking + hooks + a viewer; its own architecture writeups advise building only the subset you need |

## Sources

- agentmemory — https://github.com/rohitg00/agentmemory · https://agentmemory.homes/ · architecture review https://neoneye.github.io/agent-memory-atlas/systems/agentmemory/ · retrieval internals https://deepwiki.com/rohitg00/agentmemory/3-search-and-retrieval
- engram — https://github.com/Gentleman-Programming/engram
- Mastra Observational Memory — https://mastra.ai/research/observational-memory · https://mastra.ai/docs/memory/observational-memory
- Benchmark landscape — https://memoryatlas.dev/benchmarks · https://jakecuth.com/work/agent-memory-lab · https://awesomeagents.ai/tools/best-ai-agent-memory-frameworks-2026 · https://heybeagle.com/blog/agent-memory-benchmarks-what-longmemeval-actually-measures
- Memory MCP server survey — https://mnemoverse.com/docs/library/memory-mcp-servers-compared
- Rejected options — https://github.com/mem0ai/mem0/tree/main/openmemory · https://github.com/getzep/graphiti/blob/main/mcp_server/README.md
