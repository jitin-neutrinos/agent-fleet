# OpenCode Harness (kurama-core)

OpenCode runs in docker: `~/Work/coding-harness` (compose project, container `coding_harness`, wrapper script `~/.local/bin/opencode`).

## Where skills live

- Host: `~/Work/coding-harness/config/skills/` — bind-mounted read-only into the container as `/workspace/.skill-library`.
- Index: `~/Work/coding-harness/config/skills/INDEX.md` — the in-container agent discovers skills via this file (`grep -i <topic> .skill-library/INDEX.md`), so every new skill MUST get an entry: `- **<name>** — <one-line description>`.
- Project skills: `~/Work/coding-harness/workspace/.opencode/skills/<name>/SKILL.md` (separate from the library).

## Porting checklist

1. Copy skill folders from the Hermes side (or clone source) into `config/skills/<group>/<name>/`.
2. Append entries to `config/skills/INDEX.md` (use a `## <group>` section header for batches).
3. Verify each copied folder has `SKILL.md` with frontmatter.
4. No container restart needed while running (bind mount is live); if the container is down, skills load at next `opencode start`.

## INDEX.md extraction script

When porting many skills, generate descriptions from frontmatter instead of typing them:

```python
import os, re
lib = os.path.expanduser("~/Work/coding-harness/config/skills")
lines = []
for d in sorted(os.listdir(os.path.join(lib, "languages"))):
    p = os.path.join(lib, "languages", d, "SKILL.md")
    if not os.path.isfile(p): continue
    desc = ""
    for line in open(p):
        m = re.match(r'(?:description|summary):\s*(.+)', line)
        if m:
            desc = m.group(1).strip().strip('"').strip("'"); break
    lines.append(f"- **{d}** — {desc[:140] or '(see SKILL.md)'}")
```

Watch for multiline YAML descriptions (`description: >` followed by indented lines) — the regex grabs nothing useful and emits a bare `>`; post-clean entries matching `— >` to a fallback label.