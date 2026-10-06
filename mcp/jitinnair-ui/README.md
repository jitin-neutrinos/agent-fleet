# jitinnair-ui MCP

Read-only MCP over the ui.jitinnair.com component registry.
Three tools: list_registry_items, search_registry_items, get_registry_item.
No install tool by design: installing is `npx shadcn@latest add @jitinnair/<name>`.

Runs from source (not published to npm). Harness config:

    command: /usr/bin/python3
    args:    [<abs path>/jitinnair_ui_mcp.py]
    env:     JITINAIR_UI_BASE=https://ui.jitinnair.com

Self-check (registry must be up):
    JITINAIR_UI_BASE=https://ui.jitinnair.com python3 jitinnair_ui_mcp.py --selftest
