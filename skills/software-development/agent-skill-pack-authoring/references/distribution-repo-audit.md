# Distribution-repo audit

Recipe for answering "where do we stand" on a pack distributed as
source machine -> mirror -> (private) git repo -> hosted one-liner -> per-machine clone.
Verify EVERY leg with real output; plan docs and session summaries are context, not evidence.

## 1. Repo leg

```bash
cd <repo> && git status -sb && git log --oneline -3
git fetch -q && git rev-parse HEAD origin/main            # equal; tree clean
gh repo view <owner>/<repo> --json visibility --jq .visibility   # PRIVATE
# fresh-clone fidelity - the check that catches gitlink casualties:
rm -rf <scratch>/verify-clone
git clone -q <repo-path-or-local> <scratch>/verify-clone
find <scratch>/verify-clone/skills -name SKILL.md | wc -l  # == working-tree count
ls <scratch>/verify-clone/skills/<suspect-dir>/            # empty dir = gitlink casualty
```

## 2. Mirror/sync leg (source machine -> repo)

```bash
systemctl --user list-timers <sync>.timer --no-pager   # next / last run
journalctl --user -u <sync>.service --since -1h        # has it ever actually run?
systemctl --user start <sync>.service                  # trigger ONCE now; don't wait for the timer
journalctl --user -u <sync>.service --since -5min      # pull -> rsync -> commit -> push -> web-root refresh
cd <repo> && git log --oneline -2                      # a new "sync <ts>" commit iff content changed
```

A timer enabled but never run shows no journal entries - "not yet run" is not failure.
Triggering the oneshot once proves the whole chain immediately (use `--no-block` + poll
`is-active` from a script if you cannot block).

## 3. Hosting leg (hosted installer)

```bash
curl -fsSL https://<host>/install.sh | md5sum   # served bytes
md5sum <repo>/install.sh                        # repo copy
md5sum <web-root>/install.sh                    # the static server's copy
systemctl --user status <www>.service           # active
```

All three hashes must match, HTTP 200. If the web root is a plain copied file, confirm
the sync script's final step actually refreshes it, or the site silently serves old bytes.

## 4. Runtime clone leg (what the one-liner actually executes)

```bash
cd ~/<pack> && git log --oneline -1 && find skills -name SKILL.md | wc -l
git pull --ff-only                             # after ANY repo-level fix
```

The installer reuses `~/<pack>` when present, so a repo fix is not live until this clone
pulls. Refreshing it is part of shipping the fix, not an optional extra.

## Reporting shape

- One line per leg with its evidence; then open items split user-owned vs agent tasks
  (e.g. credential rotation = user-owned; never an agent chore - record it and stop).
- Keep commands/technical detail in the project's plan/build-log artifact; the chat
  reply itself stays plain language for a non-technical owner.
