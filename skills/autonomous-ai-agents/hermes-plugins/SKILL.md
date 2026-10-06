---
name: hermes-plugins
description: "Use when installing or troubleshooting Hermes Agent plugins."
tags: [hermes, plugins, install]
---

# Hermes Plugins

How to install and enable Hermes Agent plugins. For the broader Hermes surface, load the `hermes-agent` skill first.

## Install sources — what `hermes plugins install <source>` accepts

- `owner/repo` — GitHub shorthand (optionally `owner/repo/path/to/plugin` for a subdir)
- Full git URL — `https://...`, `git@...`, `ssh://...`, or `file://...`
- Bare community-index name (e.g. `hermes-media-studio`)
- `--ref <40-char-sha>` pins an immutable commit

## Pitfall: local filesystem paths are NOT install sources

`hermes plugins install /home/me/Downloads/my-plugin/` does NOT work. A leading-slash path is
split on `/` and interpreted as `owner/repo` shorthand — `/home/notjitin/Downloads/x` becomes a
git clone of `https://github.com/home/notjitin.git`, which fails with
`could not read Username for 'https://github.com': terminal prompts disabled`.
The cryptic git credential error means "the URL was mangled from a bad identifier", not a real auth problem.

Fixes for a plugin that lives on disk:

1. **Git repo on disk** — use the file scheme (prints an expected insecure/local-scheme warning):
   ```bash
   hermes plugins install "file:///absolute/path/to/my-plugin"
   ```
2. **Plain directory (works even without .git)** — copy into discovery and enable:
   ```bash
   cp -r /path/to/my-plugin ~/.hermes/plugins/
   hermes plugins enable <name-from-plugin.yaml>
   ```

Either way the plugin is DISABLED by default — `install` prompts `Enable 'name' now? [y/N]`
(default no); `--enable` / `--no-enable` skip the prompt. Restart Hermes afterward and verify
with `hermes plugins list`.

## Other notes

- Plugins are discovered from `~/.hermes/plugins/` (user), `<repo>/plugins/` (bundled),
  `./.hermes/plugins/` (project; needs `HERMES_ENABLE_PROJECT_PLUGINS=true`), and pip entry points.
- A plugin needs a `plugin.yaml` manifest; `requires_env:` entries are prompted at install time.
- Every install/update runs a static security scan before activation; capability declarations
  (`capabilities:` in plugin.yaml) trigger a one-time consent prompt.
- Debug a local plugin: `hermes plugin doctor <path>` (in `hermes_cli/plugin_dev.py`).
- Docs page: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
  (note: `web_extract` on this page may return empty — fall back to `curl -sL` + regex HTML strip).
- Source of truth for accepted identifiers: `_resolve_git_url` in `hermes_cli/plugins_cmd.py`.
