# Orbit API contract shapes — wrapped vs bare list endpoints

The core mixes two shapes for list responses. Getting this wrong crashes the
page, not the API: a `.map` on the wrapper object throws and the route dies
while both the backend and a curl of the JSON look healthy.

## Wrapped — `json!({ "<key>": rows })` — unwrap in api.ts

| api.ts function | endpoint | envelope key |
|---|---|---|
| billingPlans | GET /api/billing/plans | `plans` |
| apiKeys | GET /api/orgs/{slug}/keys | `keys` |
| webhooks | GET /api/orgs/{slug}/webhooks | `endpoints` |
| webhookDeliveries | GET /api/orgs/{slug}/webhooks/{id}/deliveries | `deliveries` |
| ltiDeployments | GET /api/orgs/{slug}/lti | `deployments` |
| platformOrgs | GET /api/platform/orgs | `orgs` |
| platformAudit | GET /api/platform/audit | `events` |
| agentProposals | GET /api/orgs/{slug}/agent/proposals | `proposals` |
| agentHistory | GET /api/orgs/{slug}/agent/history | `events` |

Unwrap shape: `(await request<{ k: T[] }>("GET", path)).k`.

## Bare — `format::json(rows)` — `request<T[]>` is correct

memberships, members, courses, progress, packages, aiUsage, course outline —
the loco `Scope::rows` handlers return the array directly.

## Audit method

1. In `web/src/lib/api.ts`, grep `request<...\[\]>` — every bare-array GET is
   a suspect.
2. In `core/src/controllers/`, grep `format::json(json!({` — envelope returns
   and their key.
3. Cross-check each suspect path against its controller's return shape;
   unwrap or retype. Audit ALL of them, not just the page that crashed — the
   mismatch class repeats (pricing, approvals, settings were three separate
   instances of the same class).

## QA re-seed shape (after cargo test truncates orbit_dev)

register qa-admin → POST /api/orgs (QA Academy, qa-academy) → course
(published) → module → lesson (ULS with narration scenes) → PUT ai/config
(zai, glm-5.3-flash, orbit/zai, caps) → invite instructor + learner with
explicit roles → enroll learner. Reset each account's password via
forgot/reset; probe each with its own password before concluding auth is
broken. All three accounts' credentials live in the scratch dir as 0600
files; status codes only in stdout.

## Brand assets

- Source (sibling repo): `~/Work/projects/Smartslate/smartslate-constellation/public/`
  — `logo-swirl.png` (2484×2525), `logo.png` (640×92 wordmark), `favicon.ico`.
- Orbit copies: `web/public/brand/{swirl,logo-full,favicon}.{png,ico}`,
  favicon also at `web/src/app/favicon.ico`.
- Collapsed sidebar rail: pin the img with explicit width/height/maxWidth/
  maxHeight + object-contain, container justify-center — the 2484-px source
  otherwise stretches.
