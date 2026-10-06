# Sandboxed worker isolation (bubblewrap)

When a worker agent runs a shell on your machine, its blast radius is every credential
in your environment and every mount you can reach. Isolation is cheap; use it before
the first worker sees a repo.

## Shape

`bwrap` with `--clearenv`, a tmpfs `$HOME`, and bind mounts per worker:

```
bwrap --die-with-parent --new-session --unshare-pid \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
  --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp \
  --tmpfs "$HOME" \
  --ro-bind "$HOME/.hermes/hermes-agent" "$HOME/.hermes/hermes-agent" \
  --ro-bind "$HOME/.rustup" "$HOME/.rustup" --ro-bind "$HOME/.cargo/bin" "$HOME/.cargo/bin" \
  --bind <worker_clone> <worker_clone> --bind <worker_home> <worker_home> \
  --chdir <worker_clone> --clearenv \
  --setenv HOME "$HOME" --setenv PATH <venv>:<cargo>/bin:/usr/bin \
  --setenv HERMES_HOME <worker_home> --setenv CARGO_HOME <worker_cargo> --setenv CARGO_TARGET_DIR <worker_target> \
  -- "$@"
```

Non-obvious pieces:
- `--symlink usr/bin /bin` etc. — bwrap does not create `/bin`, `/sbin`, `/lib`,
  `/lib64`; without the symlinks a shell finds no coreutils.
- The agent runtime is read-only-mounted and a PRIVATE `HERMES_HOME` holds only the
  one key that model needs. The worker's `.env` must contain that key and nothing else.
- Give each worker its OWN `CARGO_HOME` (registry) and `CARGO_TARGET_DIR`. Copy
  `~/.cargo/registry` with `cp --reflink=always` on btrfs/XFS so N workers cost one
  copy of the bytes; a shared target dir gives parallel agents lock contention.
- Keep the frozen reference and the main repo read-only or unbound: a worker that can
  write the reference can quietly "fix" the spec it is being graded against.

## Prove it before launching (a 20-line test script, run once)

Escape tests are cheap and the failure modes are silent. Assert each of these and
print PASS/FAIL per line:

| Check | Expectation |
|---|---|
| `env \| grep -iE 'TOKEN\|SECRET\|KEY\|PASSWORD'` | empty (or only the one intended var) |
| `env \| wc -l` | small — a scrubbed env, not the host's |
| `ls ~/.ssh`, `ls ~/.claude`, `ls ~/.config` | not found |
| `ls /run/media`, `ls /boot/efi` | not found (dual-boot disks must be invisible) |
| `ls /var/run/docker.sock` | not found |
| `echo x > <main_repo>/PWNED` | read-only / permission denied |
| `echo x > <frozen_reference>/PWNED` | read-only |
| `echo x > <agent_install>/PWNED` | read-only |
| `ls <main_repo>/.git`, `ls <other_worker_clone>` | not found — workers cannot see each other |
| `touch .probe` in own clone | succeeds |
| `grep -cE '^[A-Z_]+=' $HERMES_HOME/.env` | exactly 1 |
| `git push origin HEAD:master` from the worker clone | fails (no remote / permission) |

Then prove the three capabilities it actually needs, inside the sandbox:
`cargo build` (offline, warm cache), importing the reference module, and one model
call with a tool invocation. Isolation that cannot build is useless.

## Running workers in parallel

- One tracked background job each, `notify=true`. Launch them with the tool's own
  background/notify support, never shell `&` — an untracked `&` gives you no exit code
  and no completion signal.
- Record a per-worker session id file so a crashed worker can be RESUMED with
  `--resume <session_id>` rather than restarted from scratch; the context you already
  paid for is still there.
- Watch progress through an artifact the worker cannot fake: its own state DB
  (read-only, `sqlite3 file:...?mode=ro`) shows message and tool-call counts, so
  "is it actually working" is answerable without parsing prose.