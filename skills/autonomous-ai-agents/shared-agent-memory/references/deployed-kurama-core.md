# Deployed instance — agentmemory on kurama-core

Status: installed, running, verified 2026-09-13. Engine `agentmemory` 0.9.29, iii-engine 0.11.2.

## Paths

| Thing | Path |
|---|---|
| Unit | `~/.config/systemd/user/agentmemory.service` (enabled, `WantedBy=default.target`) |
| Binary | `~/.npm-global/bin/agentmemory` (global npm install, pinned version) |
| Config | `~/.agentmemory/.env` — only `EMBEDDING_PROVIDER=local` is uncommented |
| Data | `~/.local/share/agentmemory/state_store.db` (+ `stream_store/`, `iii-config.yaml`) |
| REST / viewer | `http://localhost:3111` / `http://localhost:3113` |
| Hermes MCP entry | `mcp_servers.agentmemory` in `~/.hermes/config.yaml` (54 tools, saved by `hermes mcp add`) |
| Hermes plugin | `~/.hermes/plugins/agentmemory/` (`__init__.py`, `plugin.yaml`, `README.md`) |
| Backed-up agent configs | `~/Work/scratch/pre-agentmemory-configs/` |
| Repo clone (plugin source) | `~/Work/scratch/agentmemory-src/` |

## Unit file (the working-directory pin is load-bearing)

```ini
[Service]
Type=simple
WorkingDirectory=%h/.local/share/agentmemory
Environment=AGENTMEMORY_DATA_DIR=%h/.local/share/agentmemory
ExecStart=%h/.npm-global/bin/agentmemory --data-dir %h/.local/share/agentmemory
Restart=on-failure
RestartSec=5
```

Without the pinned `WorkingDirectory`, the engine's relative `./data/state_store.db` resolves
against the startup CWD and the store silently relocates between boots.

## Commands used

```bash
# install (pinned)
V=$(npm view @agentmemory/agentmemory version); npm i -g @agentmemory/agentmemory@$V
# config
npx -y @agentmemory/agentmemory@latest init      # writes ~/.agentmemory/.env (all commented)
# wire other agents (safe preview first)
npx -y @agentmemory/agentmemory@latest connect --dry-run --all
npx -y @agentmemory/agentmemory@latest connect --all
# wire Hermes (manual; needs the piped yes)
printf 'y\n' | hermes mcp add agentmemory --command npx --args -y @agentmemory/mcp
# plugin (staged, INACTIVE)
cp -r ~/Work/scratch/agentmemory-src/integrations/hermes ~/.hermes/plugins/agentmemory
# service
systemctl --user daemon-reload && systemctl --user enable --now agentmemory.service
```

## Verification transcript (2026-09-13)

- `GET /agentmemory/health` → `"status":"healthy"`, 272 functions registered.
- Hermes one-shot saved via `mcp__agentmemory__memory_save`, read-back confirmed.
- Claude Code saved via `mcp__agentmemory__memory_save` (`claude mcp list` → `✔ Connected`).
- **Cross-read passed both directions**: Hermes returned Claude Code's token, Claude Code
  returned Hermes's token, REST ground truth showed all canaries in one store.
- Durability: a persistence probe survived two consecutive `systemctl --user restart` cycles.
- One later re-run of the cross-read failed on the Claude Code leg only because that account had
  hit its session limit (`You've hit your session limit`), while REST still served the memory.

## Known residue

- `~/data/state_store.db` — orphaned store from the first (unpinned) boot; contains only test
  canaries. Safe to remove once confirmed.
- `EMBEDDING_PROVIDER=local` downloads `Xenova/all-MiniLM-L6-v2` on the first embedding request.

## Rollback

```bash
systemctl --user disable --now agentmemory.service
rm ~/.config/systemd/user/agentmemory.service && systemctl --user daemon-reload
hermes mcp remove agentmemory
rm -rf ~/.hermes/plugins/agentmemory
# restore the agent configs from ~/Work/scratch/pre-agentmemory-configs/
```

Built-in Hermes memory (`MEMORY.md`/`USER.md`) and the holographic store are untouched by design —
`memory.provider` was deliberately left as `holographic`.
