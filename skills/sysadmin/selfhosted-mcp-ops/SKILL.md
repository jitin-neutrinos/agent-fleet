---
name: selfhosted-mcp-ops
description: "Use when probing, enhancing, or hosting self-hosted MCPs."
version: 1.0.0
author: kurama-core curator
license: internal
metadata:
  hermes:
    tags: [mcp, selfhosted, systemd, cloudflare, retrieval]
    related_skills: [kurama-work-projects, cloudflare-tunnel-hosting]
---

# Self-hosted MCP services — probe, enhance, ship

## When to Use

Use when: asked whether a self-hosted MCP/endpoint is up or functional; asked
to enhance, slim down, or speed up one of the local MCP/retrieval daemons;
asked about rewrite/port of one (e.g. to Rust); editing or republishing the
one-command installer; moving an MCP to a new domain. Not for harness-side MCP
registration (that is config plumbing, not service ops).

Applies to the local fleet of MCP/retrieval daemons (neutrinos-mcp, laya-mcp,
tool-router, openviking, and future ones): HTTP MCP endpoints behind Cloudflare
tunnels, systemd user units, one-command installers, local embedding models.

## Procedure

1. **Probe live before answering any status question.** A status question
   ("is X up/functional?") gets answered with a live probe, never from memory or
   project docs — docs rot, endpoints move. For an MCP endpoint: POST a JSON-RPC
   `initialize` with `Accept: application/json, text/event-stream`; a 200 with
   `serverInfo` name+version is definitive, and a 401/403 to the unauthenticated
   probe means ALIVE (credential-gated) — classify auth refusals as up and
   report them separately from real failures. For static files (installers): GET
   each file and check the byte count, and check BOTH the wrapper script and the
   payload it fetches — a 200 wrapper can still point at a dead domain.
2. **Separate local from public.** `systemctl --user is-active <unit>` answers
   local service state; the public endpoint probe answers reachability through
   the tunnel. Different questions, different probes — report both when the user
   asks about a public URL.
3. **Enhancement asks get research + a tiered proposal, not immediate code.**
   User asks "can we add X / make it faster / smaller?" → probe the current
   architecture (what runs, what it costs: venv size, RAM, per-query latency),
   research the alternatives, then present a measured decision table ordered by
   footprint-vs-gain, with a clear recommendation and an explicit 'not worth it'
   list. User decides; implementation follows separately.
4. **Rank enhancements by footprint-vs-gain before cleverness.** Runtime swaps
   of the same model (torch → ONNX-class) beat new stages; a rerank stage on an
   already-running local decision model beats adding a new model; anything that
   adds seconds per query (local LLM query rewriting on CPU) is usually a
   regression dressed as a feature.
5. **Gate every retrieval change on the project's eval harness.** Run the
   existing quality eval for a before/after number; keep the change only if it
   beats baseline, drop it otherwise. Never ship a retrieval change on vibes.
6. **Rewrite-language asks get a cold-start/persistence analysis first.** For a
   persistent daemon (starts once, serves for months), language rewrites buy no
   user-visible latency — per-query time lives in the C-under-Python layers
   (SQLite, numpy) and the real latency is the client's LLM. A rewrite is
   justified only when single-binary distribution IS the product (offline local
   stdio companion, tiny containers, mac/win cross-compiles) — propose that
   shape instead of a rewrite of the hosted service.
7. **Auditing a multi-stage pipeline: time stages individually, not end to end.**
   A fail-open pipeline reports one number, and that number points at the wrong
   stage. Bisect by wrapping each stage in its own timer inside one python probe
   that imports the modules directly (do not instrument the source): call the
   scoring function, then each advisory lane, then the network-touching stage.
   Then attribute cost by stubbing — monkeypatch the suspected expensive stage to
   a no-op and re-run the real entrypoint; if wall time collapses, that stage is
   the cost. End-to-end timing alone finds the cost but never the stage.
8. **A fail-open stage that returns empty is invisible, and a green self-test
   does not mean the stage ran.** Unit tests exercise the gate/rank function in
   isolation; they cannot see that the transport returns an error, the breaker is
   tripped, or the dependency returns an empty set. For every optional stage in
   an audit, report its *contribution* (how many candidates it returned), not its
   exit status: a lane returning 0 of 50 is dead no matter how fast it is. Probe
   each stage's own endpoint or dependency directly before calling it healthy.
9. **A persistent key-value state store is a liability to audit, not just read.**
   Count entries and measure key size before trusting the store. Stores keyed on
   free-text prompts accumulate whole-prompt token dumps as keys, which then
   make fuzzy key-matching mis-attribute later requests and let one entry accrue
   a huge sighting count that re-triggers its expensive path on every call.
   Report entry count, longest key, and sighting-count distribution.
10. **Installer edits: update source of truth AND public copies, then re-fetch.**
   The installer source lives in a scratch/project dir with public copies served
   by a static unit; after any edit, curl the public URL back and diff. Grep the
   payload for hardcoded URLs whenever the hosting domain changed — embedded
   defaults drift from wrappers.

## Pitfalls

- Never reuse a domain that returned 530 — it means the DNS still points at a
  deleted tunnel; the fix is re-pointing DNS, not retrying the URL.
- Don't quote idle RAM as the cost of a model — quote the venv/dependency weight
  and model files; idle RSS hides the real tax and misleads sizing decisions.
- **A high lifetime %CPU on a local MCP daemon is usually burst-on-use, not a
  leak.** `ps` %CPU is averaged over process lifetime; `top -H -p <pid>` showing
  all threads sleeping at 0.0% means idle now. The exception: high CPU AND the
  endpoint timing out = wedged (a long-running proxy died exactly this way with
  no log error) — restart first, investigate after. Audit the request log for what
  consumed the time (per-call ms lines, request volume) before restarting the
  service as a 'fix'. Memory is the real signal to watch: peak RSS ≈ sum of
  preloaded checkpoints (LRU `max_loaded` × model size) is by design, not a leak;
  a service in swap with idle threads is stale-page pressure, and a restart
  clears it cheaply.
- A research answer to "can we enhance X" ends with a recommendation and a
  validation plan (which eval, which number), so the user can say 'go' in one
  word — this user expects decision memos with measured numbers, then a gate.
- **Compare every stage's cost against the hook timeout that calls it.** An
  audit of a pipeline invoked by an editor hook or a message interceptor must
  state the caller's timeout next to the stage timings. When p99 exceeds it the
  symptom is a *silently missing* output, not a slow one — nothing errors, the
  caller just discards the result, so it never shows up in the service's own
  logs. Report "N of M runs exceed the timeout and produce no output" as its own
  finding.
- **Audit finds are only half a deliverable — order the fixes by measured cost
  removed, not by how easy they look.** The user reads the report to decide what
  to do next, so pair each finding with the single change that removes it and say
  which one removes most of the wall time. Offer to implement the top one.
- **Probe the endpoint that exists, don't trust the marketing URL (2026-10-03).**
  The cTrader "Remote MCP" setup docs point users at a snippet generated inside
  their own logged-in cTrader Web session — the public `https://mcp.spotware.com/mcp`
  responds to an initialize probe like a real MCP but is the BROKER-SALES server
  (`instructions` tells you: get_overview/get_contact_info for "how brokerages can
  get in touch with sales"), not the per-account trading server. Per-account MCP
  endpoints that are generated client-side cannot be reconstructed from public
  pages; stage the config dormant (`url: \${ENV_VAR}`, enabled: false) and wait for
  the user's snippet. A 406-to-200 initialize probe proves a server is MCP, not
  WHICH server it is — always read `serverInfo.name` and `instructions`.
- **A valid TLS certificate does not prove the hostname is served.** Wildcard
  edges complete TLS for any matching subdomain while no vhost exists behind it —
  TLS handshakes fine, every HTTP request then fails with no TLS error. Verify
  with a full POST initialize; when one host of a domain family is dead, probe
  its siblings (the shorter-label form of the same domain) before concluding the
  service is down — the fix was the hostname, not the network.

## references/

- `references/neutrinos-mcp.md` — endpoints, units, file map, enhancement
  roadmap with numbers to re-verify.
- `references/tool-router.md` — four-stage routing pipeline: stage map, per-stage
  contribution probes, the audit recipe that found its real cost, state-store
  pathologies, and the per-harness wiring map.
- `references/laya-mcp.md` — unit env wiring, the service-pinned checkpoint rule,
  the checkpoint retrain recipe, and end-to-end verification probes.
