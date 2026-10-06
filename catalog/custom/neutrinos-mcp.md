---
slug: neutrinos-mcp
title: Neutrinos Docs MCP
kind: mcp server
summary: Self-hosted docs MCP over the Neutrinos documentation portal: search_docs, get_doc_page, and list_publications served from a scheduled scraper-store-retrieve pipeline on one endpoint.
repo: jitin-neutrinos/neutrinos-mcp
site: https://neutrinos-mcp.jitinnair.com/mcp
install: curl -fsSL https://mcp.glitchzerolabs.com/install.sh | bash
attach: mcps/neutrinos-docs
---

# Neutrinos Docs MCP

An MCP server that indexes the **Neutrinos documentation portal** and serves it to any AI harness:
accurate answers and page fetch straight from the source, no scraping by the assistant, no stale
copies. It is a self-contained pipeline — scraper, store, embeddings and retrieval all live on this
fleet, refreshed on a schedule.

## Tools it exposes

| Tool | What it does |
|---|---|
| `search_docs` | Semantic search across every indexed publication. |
| `get_doc_page` | Fetch a full documentation page as markdown, by slug or URL. |
| `list_publications` | List every indexed publication. |

Also exposes documentation as MCP *resources* and ready-made prompts for retrieval-augmented
answers.

## Connect

Remote MCP over HTTPS — point any harness at:

```
https://neutrinos-mcp.jitinnair.com/mcp
```

Already wired into this fleet's store: `neutrinos-docs` appears in the Hermes, Claude, OpenCode and
Gemini legs of the installer.

## Self-host / rebuild

```bash
curl -fsSL https://mcp.glitchzerolabs.com/install.sh | bash
```

The installer sets up the container that loops daily (14:00 IST) over the sitemap-diff scraper and
catches up on startup if a run was missed. Source layout and runbook: private repo
`jitin-neutrinos/neutrinos-mcp`.
