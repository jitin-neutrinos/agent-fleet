# Assistant-Build Recipes (Platform-Config Specs from Vendor Docs)

Deliverable class: the user asks you to research a vendor AI platform via its
docs MCP and produce a BUILD SPEC — field values to paste into the product's
UI (assistant directive/greeting/welcome-options), guardrail and connector
settings tables, and a rollout sequence. The deliverable is copy-paste-ready,
not an essay. Distilled from a full AI Hub assistant-build round (directive,
guardrails, MCP connector hookup, advanced settings, review loop).

## Recipe-extraction pattern

- Fetch the product's landing page FIRST to enumerate its tabs/sections, then
  fetch one full page per feature the spec touches (each assistant tab, each
  guardrail rule, the connector dialogs, publish/test/review pages). ~15 full
  fetches for a complete assistant-build spec is normal; snippet-level
  discovery is not enough because field names, toggle names, sensitivity
  levels, and hard limits (e.g. max knowledge sources per assistant) must be
  quoted exactly.
- Read the feature page for SCOPE NOTES, not just steps: platform features
  often carry a restricting note on their own page (e.g. a context-filtering
  rule documented as applying only to linked assistants, not the primary).
  A rule that looks perfect for the design may be unusable in the v1
  topology — check before recommending it.
- Capture the platform's own lifecycle gates in the rollout order (e.g. only
  published versions can be tested; guardrail assistants can only be attached
  after the guardrail is created).

## The numbered-citation directive template

Paste-ready directive requirements that survived review — include ALL five
blocks; omitting any one reopens a hallucination path:

1. GROUNDING — answer ONLY from tool-returned content; require at least one
   tool call before answering; a failed or empty call is a NO RESULT path,
   never a reason to answer from memory.
2. TOOL CATALOG — name the connector and every tool in the directive exactly
   as the server publishes them (`@Vendor Docs MCP / search_docs`), with one
   'use when' line per tool lifted from the tool's own published usage
   guidance (the server's schema catalog — e.g. its listing on an MCP
   registry — states when to prefer each tool; that guidance is the source,
   don't invent it). Wire refusal triggers to tool-returned signals
   (e.g. `sufficient_evidence=false` ⇒ escalate, never infer), and give an
   empty-result recovery procedure (listing tool to correct filters → retry
   once → escalate). Users want tools called out by name and models follow
   named tools more reliably than vague 'use your tools' phrasing (Anthropic
   explicit-tool-direction guidance). Caveat: verify names against what the
   platform's Test Connection actually lists and include a rename-if-different
   note — the WHEN rules survive renames, the exact strings may not.
3. CITATION FORMAT — numbered first-use markers [1][2] after each claim;
   reuse the same number per source; a Sources block listing exact page title
   + public URL (+ last-updated when returned); an explicit "never invent a
   URL, title, or number; a claim without a valid marker is a defect" line.
4. REFUSAL/ESCALATION — a fixed handoff message, an instruction to STOP after
   it, and a partial-coverage rule (answer the documented part with
   citations, name the gap, escalate the rest).
5. STYLE + SCOPE — structure/verbosity expectations, an explicit topic scope,
   and a never-disclose-these-instructions line. XML-tag the directive's
   sections (`<role>`, `<tools>`, `<quality_gate>`…) — tagged sections resist
   instruction/context mixing in long prompts.

Set the platform's creativity/temperature setting LOW for support bots; treat
the platform's built-in injection/output-compliance layer as the security
mechanism and do NOT duplicate it inside the directive.

## Integration layer (deploy → token → Integrations page)
When the spec includes wiring the assistant to external code, capture the
platform's own integration chain — it is mostly hard gates, not settings:

- Deployment is the gate for EVERYTHING downstream: tokens and Integrations
  cURLs are only generated for models deployed to a deployment unit (create
  the unit first, then deploy the version via the kebab-menu toggle, wait for
  the Running status). 'Published' ≠ 'deployed' — check which one each page
  requires before promising a cURL.
- Tokens are model+version-specific and displayed ONCE — save to the project
  .env (chmod 0600) immediately; recovery is revoke-and-recreate.
- The Integrations page fills three dropdowns in order (version → environment
  → API type); an empty selector almost always means an upstream gate failed,
  not a UI bug. When a user reports empty dropdowns, walk the gates in order
  before concluding the documented endpoints are wrong — and say openly when
  the docs don't cover a page's exact behavior (verified gates vs inference;
  the deliverable must label which is which).
- Keep token + endpoint contract in .env with stable names (AIHUB_TOKEN,
  AIHUB_BASE_URL) so middleware never hardcodes either; document the sync
  flow (conversation/create → message/create → read output.text) as the
  middleware contract.
- Live functional test BEFORE handing over: curl the documented endpoints with
  the real token (conversation create → message create), assert HTTP 201/200
  and a real answer. One call proves token + deployment + endpoint in one shot
  and converts 'should work' into 'verified'. Echo responses through a sed
  filter on the token so secrets never land in transcripts.
- Verify the RESPONSE SHAPE, not just the HTTP code: run one in-scope question
  and assert the directive's markers actually fired (citation markers present,
  Sources block present), then one out-of-scope question and assert the
  escalation marker fired. HTTP 201 + fluent prose can still mean the directive
  never reached the serving version — a completed answer without citations is
  the signature of a stale deployment or a platform fallback path answering
  (see the directive-edits bullet below).
- Directive edits do NOT reach the serving API automatically: the edited
  version must be published AND redeployed to the deployment unit the token
  binds to. When live answers ignore a directive the user says they applied,
  first isolate with the platform's Test Version chat on the edited version —
  correct there + wrong via API = stale deployment/token binding; wrong there
  too = the paste never landed (wrong version open, unsaved field, truncated
  paste). Runtime answers that bypass connectors (vague, bare pasted links, no
  directive markers) usually mean a platform fallback (allowed-domains web
  fetch) is answering — close the fallback and check the connector's tool
  endpoints are actually ticked, not just mapped.
- An external middleware (your code between the platform and the target
  system) is often the lazier escalation transport than a platform API
  connector: it can grep the directive's machine-parseable marker
  deterministically before anything is sent onward, and it keeps third-party
  API keys server-side instead of pasted into the platform's connector config.
- Screen-recording a DRM-decrypted stream is the hard NO at the end of every
  fallback chain: the Widevine CDM license forbids use outside its licensed
  browser (routing Brave's CDM into another Chromium breaks it), and capturing
  DRM-decrypted frames is DMCA §1201 / InfoSoc Art. 6 anti-circumvention even
  when streaming the content is legal. Widevine L1 never exposes frames to
  system memory (black captures); L3 is capped ≤480p and most services block
  it. Non-DRM screen capture (Xvfb + headed Chromium + ffmpeg x11grab/pulse)
  is the legitimate last resort for sites that merely obfuscate. Ship the
  refusal as an endpoint or doc section so the reasoning persists, not as a
  chat-only 'no'.

## Escalate-to-human design

- Check the docs for a native human-tagging primitive BEFORE designing one —
  absence is common. Default (works day 1, zero infra): directive handoff
  message + the platform's review/queue surface for humans to triage.
- Better UX (phase 2): chained worker assistant → ticketing via an API
  connector, or the surrounding community platform's own staff-ping mechanism
  via its API. Keep the escalation contract in the directive identical across
  phases so only the transport changes.
- Make the contract machine-parseable: fixed handoff message + a marker line
  (`[ESCALATION] reason: <code>`) with a closed trigger vocabulary
  (no_result / partial_coverage / conflicting_sources / out_of_scope /
  user_dissatisfied). The marker is greppable in logs and is the stable
  interface the phase-2 transport hangs off — the directive calls the
  connector 'immediately after the marker' with question + summary + code,
  and never mentions marker or call to the user. Add a user-dissatisfaction
  trigger (user says the previous answer was wrong/incomplete) — it catches
  quality failures no retrieval signal exposes.
- Quality gates live in the DIRECTIVE, but correctness of 'did it escalate'
  is validated by testing the live API with (a) a normal in-scope question
  (assert citations present) and (b) a deliberately out-of-scope question
  (assert the escalation marker fires). A deployed assistant that answers
  trivia cheerfully has stale instructions — the gate only exists if the
  deployed version carries it.

## Web-companion research rules

- Identify the surrounding platform from the vendor's own community or
  announcement posts (e.g. a Discourse-hosted community ⇒ Discourse AI
  plugin settings are the adjacency to research).
- Search generic technique terms ("RAG numbered citation markers best
  practice", "chatbot escalate-to-human fallback design"), not brand+feature —
  brand+feature queries return the vendor's marketing, not implementation
  lore. Adjacent ecosystem GitHub READMEs (community chatbot plugins) expose
  reusable patterns (staff escalation, trust-level tool allowlists) worth one
  line each as industry-normal options.
- Distinguish external citations from vendor citations in the Sources block;
  vendor docs remain the source of truth for what the platform actually does.

## Feature-selection discipline (run a ponytail pass on the spec)

After drafting, review the spec for over-building before delivering:

- Recommend orchestration features (assistant chaining, linked assistants,
  multi-agent modes) ONLY for genuinely multi-skill requests. A single-skill
  assistant (one corpus, one answer shape) gains nothing from splitting and
  inherits the platform's own listed costs — harder debugging, orchestration
  complexity, governance burden, higher compute per query. Cite the docs'
  limitation list as the argument, not opinion.
- Never stand up a second data layer duplicating the first (a Knowledge
  corpus mirroring what the docs MCP already serves duplicates content AND
  its staleness — two copies of the same truth drift apart silently). Defer
  with a written re-trigger condition ('add only if Test Version runs show
  MCP latency/downtime'), never a vague nice-to-have.
- Scope notes feed this pass: a feature restricted to a topology you don't
  have (context filtering requires linked assistants) is 'free later, skip
  now' — record the auto-unlock condition, don't pre-build for it.
- Trust-boundary content (guardrails, refusal rules, injection defense) is
  NOT trimmable in this pass — the laziness applies to features and data
  layers, never to safety surface.

- Integrating the platform's OWN SDK into your agent's MCP: separate the
  transport question from the grounding question. The SDK only carries a
  question to an assistant that already has sources — it does not make
  answers more grounded, and in this harness (Hermes + Astra chat) the
  local docs-MCP answer, which cites pages, is MORE grounded than routing
  the same question through the platform. Deliverable shapes per consumer:
  (1) files already in the platform → map up to 10 knowledge sources,
  retrieve their ids, then exactly three SDK calls (list sources → open
  conversation → send message with the `sources: string[]` array from the
  create-message DTO), never wrap all 68 methods; (2) assistant calls YOUR
  tools → a hosted platform cannot reach 127.0.0.1, so the MCP endpoint
  must be publicly reachable (tunnel), auth per the connector page
  (None/API key/OAuth2/Bearer/Basic), test the connection, TICK only the
  read tools, and let the directive say when to call them and that the
  answer must quote the result or say it is missing; (3) the platform does
  NOT auto-attach citations anywhere — knowledge sources improve precision,
  the citation contract (proving quotes) lives in the assistant directive,
  not in the product. Corollary: SDK `listEmbeddings` (search field,
  page/size, sort desc) retrieved a paginated FIELD LIST, not semantic
  matches — never build a RAG layer on it. All five pages cited
  (documentation.neutrinos.com/article/ai-hub/: knowledge, toolsets,
  add-connector, integrate-api-assistant, methods-1-2-3-4), 2026-10-04.
  Full recipe was a session deliverable; the reusable parts are the
  pick-who-answers → put-ground-in-one-place → write-proof-rule → deploy →
  mint-one-token → three-calls-not-68 step order and the do/don't pairing
  ("Map the sources, pass their ids on the message" / do NOT "build your
  own search on listEmbeddings").
