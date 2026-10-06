---
name: ctrader-stack
description: Use when doing cTrader bot or MCP work on kurama-core.
version: 1.0.0
author: notjitin
license: MIT
metadata:
  hermes:
    tags: [ctrader, trading, xauusd, mcp, docker, spotware]
    related_skills: [hermes-agent, claude-code, ponytail]
---

# cTrader stack on kurama-core

Installed 2026-10-03 for XAUUSD swing+scalp bot work.

## When to Use

Load this skill for ANY cTrader task on kurama-core: building or editing a cBot, backtesting/optimising, wiring a cTrader MCP into a harness, or placing orders via cTrader. It records the install layout, the Linux constraints that rule out the obvious route, and the encoding/quirk traps that silently produce wrong-sized orders.

Do NOT load it for TradingView-only chart work.

## What's installed where

| Piece | Hermes | Claude | agy | opencode | Notes |
|---|---|---|---|---|---|
| `ctrader-cli` skill | `~/.hermes/skills/software-development/` | `~/.claude/skills/` | `~/.gemini/config/skills/` | `~/.config/opencode/skills/software-development/` | 8 files each |
| `ctrader-mcp-servers` skill | same | same | same | same | 13 files each, incl. 5 stdlib python helpers |
| cTrader Console Docker | — | — | — | — | `ghcr.io/spotware/ctrader-console@sha256:285484fad4…` |
| cTrader Remote MCP | `enabled: false` | disabled | disabled | `enabled:false` | dormant, awaiting token |
| mikeh22 tradingview-mcp | active | active | active | active | unauthenticated, needs TV login |

Fleet store: MCP defs in `~/Work/infra/agent-fleet/mcp/{hermes,claude}.list` + `opencode.json` + `gemini.json`.

Harness skill-discovery contracts matter — Claude Code reads only depth-1, agy reads only flat, opencode globs recursively, Hermes supports categories. Copy accordingly or the skill silently never loads.

Install-loop lessons (2026-10-03, mirror these for ANY skill install to all harnesses):
- `skill_manage` create always lands the skill at the TOP-LEVEL `~/.hermes/skills/<name>/` — the Hermes category dir goes in frontmatter (`metadata.hermes.tags`/related_skills), never in the path. A mirror loop that assumes `skills/software-development/<name>/` fails with `cp: cannot stat` — find the real path with `find/search` first.
- Verify each harness leg by probing, not by file count: after mirrors, `~/.tool-router/route "<task phrasing>" | grep -i <skill-name>` must surface the skill. First reindex shipped an index without it.
- Register MCPs in the 4 harness configs in the same pass; back up all configs first (`~/.config-backups/<tag>/`). MCP defs are metadata — no licence issue, unlike vendored skill file copies.
- Direct agent writes to `~/.hermes/config.yaml` are refused by design ("Agent cannot modify security-sensitive configuration"). Use the guarded path: `hermes config set --force mcp_servers.<name> '<json>'`, then `hermes config get` to read back provenance.
- Verify a Docker-based MCP with a minimal stdio initialize handshake before wiring it into configs; verify image work after pull with `docker run --rm <img> --version`.

## LICENCE TRAP — read before adding to the fleet store

`spotware/ctrader-skills` is **`license: Proprietary`**. COPYRIGHT.md: "reproduction, modification, and distribution are governed exclusively by the Spotware EULA" (https://www.spotware.com/eula/).

`~/Work/infra/agent-fleet/sync-from-desktop.sh` rsyncs `~/.hermes/skills/` → the fleet repo (`jitin-neutrinos/agent-fleet`, private GitHub) on a timer (`agent-fleet-sync.timer`, every 6h at :15). **Any proprietary skill installed into `~/.hermes/skills/` gets auto-pushed unless explicitly excluded.** Status as of 2026-10-05: the A/B/C licence decision was ask-blocked, the 2026-10-04 00:15 sync fired, and both Spotware skill dirs are committed to the repo (fleet git has no ctrader exclude in sync-from-desktop.sh). OUTSTANDING: confirm Jitin's call (A = add `--exclude` rules for `skills/software-development/ctrader-cli/` and `ctrader-mcp-servers/`, B = leave as committed, C = uninstall); do not treat the sync as sanctioned redistribution until he answers.

Lesson: answer a licence gate in-session — a blocking question left open is silently closed by the next timer run.

Lesson: check `license:` in a skill's frontmatter before installing it into `~/.hermes/skills/` when a sync timer mirrors that tree anywhere.

## Linux constraints (why not the obvious route)

- **Local MCP is unusable** — Spotware's `ctrader-local-mcp` inherits auth from a running cTrader Windows/Mac desktop session. kurama-core is Nobara Linux, no such desktop. Only Remote MCP (HTTP, per-account token from cTrader Web → Settings → Remote MCP) is viable first-party.
- **The Docker image is the workaround.** `ghcr.io/spotware/ctrader-console` is the full Algo runtime on Linux — .NET SDK (so `create`/`build` work), Python 3.12 + ash, algohost. So backtest/optimise/run all work headless, which is exactly what Local MCP would have given.
- Pin the tag or digest. `latest` moved to 5.10.1.0 / .NET 10 / Ubuntu 24.04 while the repo README still said 5.9.11.

## Commands that actually work

```bash
docker run --rm ghcr.io/spotware/ctrader-console:latest --version
# → cTrader Command Line Interface / Version: 5.10.1.0
```

Credentials go in a `--pwd-file`, never `--password` on the cmdline. Auth conventions are **not** interchangeable: batch mode needs `--ctid` + `--pwd-file` and rejects `--password`; interactive needs `--ctid` + `--password`.

## Helper scripts (the parts agents get wrong)

`~/.hermes/skills/software-development/ctrader-mcp-servers/scripts/` — 5 stdlib-only scripts, all pass `--self-test`:
`units_encoding.py`, `pip_math.py`, `position_sizing.py`, `tiered_margin.py`, `conversion_rate.py`.

Subcommands take flags, not positionals: `units_encoding.py lots-to-cents --lots 1 --lot-size 100` → `{"cents":10000}`.

**Critical encoding fact (Remote server):** every `volume` is an integer count of **cents** of base asset, 100× the Local server's units for the same lot. Prices are **pipettes** (`price / 10^pipDigits`). Money is `10^moneyDigits`. Getting these wrong silently sends wrong-size orders.

Skill frontmatter claims `Requires Python 3.12+` but the scripts are pure stdlib with no 3.12-only syntax — verified working on the host's python3.11.

## Top quirks from the Spotware ledger (audit 2026-05-14)

- **Q-R1** `period` enum is **9** values, not 26: `M_1 M_5 M_15 M_30 H_1 H_4 D_1 W_1 MN_1`. Anything else = Zod `-32602`.
- **Q-R4** MARKET orders **reject absolute SL/TP** — use `relativeStopLoss`/`relativeTakeProfit`.
- **Q-R10** `amend_position` omitting a leg **REMOVES** it.
- **Q-R11** history endpoints lag after mutations — verify via the mutation response object, not a re-query.
- Open API caps: 50 req/s realtime, 5 req/s historical.

## Outstanding items (blocked on credentials, not on agent action)

- **cTrader Remote MCP** — registered in all 4 harnesses as `ctrader-remote`, `enabled: false`. Needs URL + per-account token from cTrader Web → Settings → Remote MCP. Endpoint is NOT public: `https://mcp.spotware.com/mcp` is the broker-sales MCP (`get_overview`, `get_contact_info`) — probed 2026-10-03, confirmed wrong target. Jitin will supply his own config snippet later; parsing it is step one. Do not manufacture an endpoint from any other remote MCP URL.
- **mikeh1975/tradingview-mcp** — installed, handshake verified, unauthenticated. Needs one-time TV login with a throwaway account (mikeh-22 image stores a ~25-day session token). Registry: `mikeh1975/tradingview-mcp` on Docker Hub.
- Config backup of all four harness configs pre-change: `~/.config-backups/20261003-ctrader-mcp/`. MCP defs appended to fleet store `mcp/hermes.list`, `mcp/claude.list`, `mcp/opencode.json`, `mcp/gemini.json`.

## TradingView MCPs — hard boundary

`tradingview-mcp` (mikeh1975 image) wraps TradingView's **undocumented private API** using your TV credentials (session token ~25 days). Throwaway TV account only. It is **research-only — it cannot place cTrader orders.** No TradingView MCP can; TradingView has no official public data API and no broker order routing.

XAUUSD feed mismatch: TradingView `FX_IDC`/`OANDA:XAUUSD` ≠ your broker's cTrader XAUUSD. Different spread, rollovers, quote convention. Broker-specific numbers (ATR floors in pips, spread caps in points) must be derived from cTrader's own historical data, never from TradingView.