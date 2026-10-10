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

## v2.1 memberships payload (workstream C)

`GET /api/me/memberships` items now carry an optional `plan` object resolved
per org via `billing::resolve` in that org's scope:

```json
{
  "org_id": "uuid", "org_name": "…", "org_slug": "…", "role": "admin",
  "plan": {
    "code": "ind-creator", "name": "Creator", "status": "active",
    "source": "personal | org | trial",
    "period_end": "…", "expires_at": null,
    "seats_blocked": false
  }
}
```

`source` = `personal` when the caller holds their own subscription row,
`trial` when the org has no subscription (trial default with 14-day expiry),
else `org`. `seats_blocked` mirrors the org-level soft-block. The Settings →
Organizations card (`organizations-card.tsx`) renders it; `remove_member`
self-leave answers 409 `cancel_personal_first` when the caller has an active
personal subscription in that org.

## Billing resolve/seat_gate contract (workstream B)

- `billing::resolve(txn, org_id, user_id)` → `{ org, personal, covered,
  seat_exempt }`. `personal` is ONLY the caller's own row; the "individual
  org" fallback (no org plan, a member's personal sub) shapes `org` — it must
  never write `personal_ent`, or every new member looks seat-exempt.
- `billing::seat_gate(txn, org_id, user_id, role)` — advisory lock + count in
  the CALLER's txn; race-safe only when gate + membership INSERT + commit share
  that one transaction (invite, LTI JIT, SSO JIT, agent tool all do).
- `billing::apply_event(txn, org_id, sub_user_id, …)` keys the UPDATE on the
  subscription's own `(org_id, user_id)` — a personal webhook never touches the
  org row. `razorpay_subscription_id` resolves both fields in billing_http.
- Trial default: 5 seats / 100k tokens, expires at `orgs.created_at + 14d`;
  an org whose only plan is a member's individual sub reads as audience
  `individual` with 1 staff seat (not a free 5-seat team org).

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
