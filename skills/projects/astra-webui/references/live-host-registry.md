# Surfacing a live host registry in the UI

For any UI affordance that must track what the host SESSION supports (slash commands, tools, skills, models) rather than a hand-maintained list. The failure mode this prevents: a copied list that looks correct today and is wrong after every `hermes update`, with nothing to signal the drift.

## The shape

**Read the host's own registry; never transcribe it.** This repo carries ZERO edits to `~/.hermes/hermes-agent` (owner mandate — `hermes update` must not be able to erase the work), so the extension point is an *import from the proxy*, not a new upstream route.

## CHECK FOR A NATIVE CATALOG RPC BEFORE DUMPING PYTHON

The gateway already serves a **richer** catalog than any Python import, and importing the registry silently omits part of the command surface. Prefer, in this order:

1. **`commands.catalog` RPC** (`tui_gateway/methods_tools.py`) — the registry commands PLUS **user `quick_commands`, plugin commands, and skill-derived commands** (`scan_skill_commands()`), resolved against the *calling session's* profile and workspace, with categories and per-command desktop meta. Discovery failures land in a `warning` field rather than throwing. This is the source of truth for a palette.
2. **`complete.slash` RPC** — the same union for a typed query (built-ins + quick commands + skills).
3. **`hermes_cli/commands.py::COMMAND_REGISTRY`** (102 `CommandDef` records: `name`, `description`, `category`, `aliases`, `args_hint`, `busy_policy`) — **built-ins ONLY.** Reachable from a WebSocket client already authenticated to the gateway, so prefer it over spawning python; keep the python dump only for surfaces with no live gateway socket (e.g. a proxy route), and treat it as a *subset*, never as "the command list".
4. **`_SLASH_DISPATCH` in `cli.py`** — names only, poorest map. Never a palette source.

**Symptom of getting this wrong:** the palette lists 102 built-ins and looks complete, while every `/skills`-style and skill-derived command is missing — and nothing signals the gap, because the built-ins all render fine. If the ask is "show me the commands", an incomplete catalog that appears complete is worse than an obviously short one.

Probe it read-only before designing anything:

```bash
cd ~/.hermes/hermes-agent && ./venv/bin/python -c "
import json
from hermes_cli.commands import COMMAND_REGISTRY
print(json.dumps([{'name':c.name,'description':c.description,'category':c.category,
  'aliases':list(c.aliases or ()),'args_hint':c.args_hint} for c in COMMAND_REGISTRY], indent=1))"
```

## Server (`server/<feature>-registry.mjs`)

Three properties make it safe to put in front of a chat box:

1. **Cache key = mtime of the host source file.** A registry change invalidates the cache with no version bump to track and no restart.
2. **Stale-while-revalidate.** Return a usable cache immediately; run the dump behind it. Opening the palette must never be slow (measured here: 39ms cold, 0ms warm).
3. **Fail-open.** A python error, timeout, or unparseable payload returns the last good copy, then an empty list. Never throw, never 500 — a convenience surface that can block the composer is worse than no surface.

Spawn with `execFile` (NOT `exec`/shell), `cwd` = the host repo, an explicit timeout, and a `maxBuffer` sized for the payload. Belt-and-braces disk cache in a project-local `.cache/` so a restart does not re-spawn python on the first request.

Normalise every record defensively — the host may add fields or return odd types, so `normaliseCommand()` must never throw:

- `String(raw.x ?? "")` + `.trim()`, lowercased name.
- **Filter `null`/`undefined` BEFORE `String()`** — `String(null)` is the literal `"null"`, so a null alias silently becomes a real-looking alias in the palette. This was a genuine bug caught by a junk-types check.
- Drop records with no usable name; default a missing category to `"Other"` rather than rendering an empty badge.

Register the route in `server/hermes-proxy.mjs` as an early intercept in `handleHxProxy` (match that file's existing style — read it before editing). It must sit behind the same auth the neighbouring routes use: a `401` on an unauthenticated probe is CORRECT and proves the route is wired.

## Client

- `fetch<Feature>(force = false)` with **module-scope memo** so repeat opens are free, plus an `inflight` promise so concurrent callers share one request. On error, return the cache or `[]` — never surface a throw into the composer.
- Keep pure logic out of the component: a check file that imports a component pulling a Vite `?raw` asset dies with a module-not-found that reads as a code bug. Put ranking/normalisation in `src/lib/<feature>.ts` and import that from both.
- **Ranking for a command filter:** exact name > name prefix (penalise length) > name subsequence > alias exact > alias prefix > alias subsequence > description substring. Stable-sort by score then original index so equal matches do not reshuffle between keystrokes.

## EXECUTING a command, not just listing it

Listing commands is half the feature. A command that only inserts text into the composer is not wired — it goes to the agent as prose. To actually run one, use the **same RPC the TUI uses**:

`slash.exec` — params `{session_id, command}` (`SlashExecParams` in `tui_gateway/contracts/tools_commands.py`). Returns `{output, warning}` for most commands, and **a dispatch directive instead of output** when the gateway re-routes rather than executes (a skill, an alias, a prefill). Handle all three shapes: `output` is text, `type`+`message`/`display`/`target` is a reroute, neither is an error. Render a reroute labelled as such instead of pretending the command ran.

`command.dispatch` — params `{name, arg?, session_id?}` — is the underlying resolver, called by `slash.exec` for pending-input built-ins. A few commands are explicitly **blocked** from the slash worker (skill commands return 4018 telling you to use `command.dispatch`; snapshot restore mutates live config). Let `slash.exec` surface those errors verbatim rather than wrapping them.

**Read-only readouts belong in one dismissable surface.** Curated commands (`/status`, `/skills`, `/usage`, `/compact`, `/sessions`, `/tools`, `/plugins`, `/memory`, `/help`) all resolve to the same thing — text from the slash worker — so implement ONE table-driven panel, not N bespoke components. The command→(title, blurb) mapping is a data table; the component is shared. Nine components is nine places for one bug to hide. Keep commands that already own a live surface (`/bg`, `/steer`) and commands that mutate session/turn state (`/model`, `/reasoning`, `/stop`, `/new`) OUT of it.

Two routing rules that bite:

- **Derive the surface check from the table, not a second hardcoded list** — `surfaceFor(input)` reading the same map the panel renders from. Two lists drift on the first addition.
- **Parser whitespace:** `"/  status"` must resolve. `text.slice(1).split(/\s+/)` yields an empty FIRST token after the leading slash, so the lookup misses. Use `.trim().split(/\s+/).filter(Boolean)`. Same family as the `String(null)` trap above — both are "the matcher rejects well-formed input", both want a junk-input check next to the happy path.

The curated nine are NOT everything, but the remainder stay composer-reachable via the slash palette — never a permanent "All commands" trigger in the composer; the owner removed that button. Removing a UI affordance must take the WHOLE chain in one pass: button JSX, its state, the modal render + import, the component file itself, and EVERY CSS rule. Grep both the class name and the component name across `src/` with a full listing (never `head -N` — a truncated hit list leaves orphan rules that ship). Then build, deploy, and verify the SERVED bundle no longer contains the class. Exclude `/bg` and `/steer` (live-turn semantics) and `/quit`/`/exit` (end the session) from any dispatch surface.

**Owner preference, standing:** surfaces are **dismissable** (collapse-to-header plus an X), and the status chip must derive from the exec RESULT, not the item's optimistic `"running"` — otherwise the spinner sticks forever because the panel owns the call, not the parent.

## Trigger anchoring

A `/` palette must be **line-anchored**, not free-floating: match `/(?:^|\n)\s*\/([^\s/]*)$/` against the text before the caret. A mid-sentence slash is prose, a path, or a date (`see /usr/bin`, `ratio 1/2`) and hijacking it eats the user's text. Once the token takes a space it is a command *with its argument*, so the palette closes and the user keeps typing.

`Enter` must only be intercepted while a real selection exists, otherwise it falls through to the composer's own submit.

## Verify

For an exec path, "the palette opens" is not "the command executes" — prove the readout/result stage too before claiming the feature works. If a headless Enter will not submit (React needs a synthetic `keyCode:13` keydown; `press('Enter')` often drops), run a stage-by-stage diagnostic once, then report the probe INCONCLUSIVE — never upgrade an open-state check into an exec-path claim.

Server module directly (`node -e "import('./server/<f>.mjs').then(...)"`) proves the dump and cache without auth. A `401` on the HTTP route proves wiring, not content. The rendered palette needs the app session — if you cannot authenticate, say plainly which layer you proved and which you did not, rather than opening the report with "verified".