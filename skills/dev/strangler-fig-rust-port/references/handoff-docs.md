# Session handoffs for a multi-session port

A handoff prompt is the bridge between sessions that each own a slice of one
long port. Its job: let a cold session reach verified ground truth in minutes
and continue without re-deriving rules that were paid for already.

## What goes in (write it as ONE copy-pasteable document)

1. One-paragraph project definition — what is being built, where the work
   lives, where the frozen reference spec lives.
2. Non-negotiable rules — distilled as rules, not history. The no-subagents
   mandate, the file-by-file loop, the line-count gate, the adversarial-check
   rule, the re-read-the-reference rule, plus the owner's communication
   preferences (plain language, no jargon in chat, technical detail in files).
3. Current state table — crate/module → what it ports → key evidence, plus
   the summed workspace test count and parity-suite status as of HEAD.
4. The verification suite — exact commands with expected numbers, runnable
   cold (workspace test sum, each parity compare, audit script, load, clippy,
   slop). A new session runs this FIRST and reconciles against `git log`.
5. Key paths — repo, reference fork, protocol/ledger docs, parity harness,
   any venvs or model dirs, env-var names the binaries read.
6. Hard-won gotchas — the pitfall list distilled to rules (this overlaps the
   porting skill deliberately: the handoff carries the ones that cost a
   debugging session most recently).
7. What's next — dependency-ordered queue, pointing at the scope/plan doc.
8. Session-start checklist — read docs, run suite, check `git status`, route
   the task, load the methodology skill, port.

## Rules that cost a handoff to learn

- Save the handoff as a committed file in the repo (e.g. HANDOFF.md) as well
  as pasting it into chat — the file survives independent of any chat surface
  and the next session can be told to read it instead of trusting a paste.
- Sessions run in parallel on the same repo: before ANY fix, `git log` and a
  re-run of the failing suite come first — a sibling may have fixed it, and a
  patch applying cleanly onto the fixed file proves nothing about attribution.
- The handoff is a snapshot, not authority: on resume, reconcile real HEAD
  and the ledger against it; the docs lag commits. Fix out-of-order rows and
  stale totals while reconciling — the ledger is the audit trail.
- Scope grows on owner directive: when the mandate expands from "front-load
  the core" to "port everything", update the handoff to say so and point at
  the measured scope doc — do not leave the old narrower framing in place.
- Keep the "what's next" queue tied to the scope doc's arc order, not to
  memory of what seemed next when the handoff was written.
- After closing an arc, refresh the handoff in the SAME session (state table,
  HEAD, suite list, next queue) — a handoff still describing the previous
  arc's row count sends the next session reconciling phantom drift, and the
  done-gate flags the state mismatch as unsupported claims.
- Record research/optimization plan docs (RESEARCH-<topic>.md) in the handoff's
  state section with their layer names and default-off status — they are the
  "why" behind later bench-gated work and must not be rediscovered by re-search.
