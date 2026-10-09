# Multi-tenant Postgres + cookie-auth app: read-only security probes and privileged-account design

Run before designing privileged access or trusting "RLS is on". Everything here is read-only. Substitute the app role for your project (`orbit_app` in Orbit).

## Probes (probe → what it catches)

- Who bypasses RLS: `select rolname, rolsuper, rolbypassrls from pg_roles where rolname !~ '^pg_'` — a superuser/owner pool role skips every policy, so "works in dev" proves nothing; isolation tests must assume the app role with `SET LOCAL ROLE`.
- Which tables are fenced: `select relname, relrowsecurity, relforcerowsecurity from pg_class where relkind='r' and relnamespace='public'::regnamespace` — rls=false tables (users, job queues, migrations) are fully readable by the app role; owners bypass policies unless FORCE is set.
- What the app role may touch: `information_schema.role_table_grants` and `information_schema.column_privileges` for the role — a table-wide grant on a credentials table (password hash, api key, reset and magic-link tokens) sits beside fenced tenant tables.
- Default privileges: `select defaclrole::regrole, defaclobjtype, defaclacl from pg_default_acl` — `ALTER DEFAULT PRIVILEGES` hands the app role CRUD on every future table, so a sensitive new table needs an explicit REVOKE plus a CI assertion.
- Constraints and validators: `select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid = '<t>'::regclass`, then read the code-side validator — a permissive one (any lowercase `a/b` string accepted as a secret reference) is a finding.
- Cookie flags: POST the login with `curl -si`, grep `set-cookie`, redact the token — HttpOnly, SameSite, Secure, Max-Age. SameSite is scoped to the registrable domain, so sibling subdomains are same-site; unsafe methods also need a `Sec-Fetch-Site: same-origin` (or Origin) check, which page JavaScript cannot forge.
- Role checks: grep for deny-lists (`role != "learner"`) — a new role string fails open; use allow-lists.
- Throttling: grep for rate-limit/throttle and time a failed login — if only the password hash cost slows guessing, there is no throttle.
- Revocation: list token lifetimes (JWT, signed content URLs) — stateless tokens cannot honour suspension or demotion; the check must be server-side on the request path.
- Client handlers: grep the client's global 401 handler before choosing 401 vs 403 for a new gate.

## Probing hygiene

- Probe every test account with ITS OWN password before concluding auth is broken; one shared wrong password across accounts reads as total failure. Recover a lost password through the app's own forgot/reset flow (the `smartslate-orbit` skill has the exact steps).

## Operator-grade ("platform admin") account — rules that held up against GitLab Admin Mode, GitHub sudo mode and Google Access Approval

- Separate table keyed by user id: never a column on the unprotected users table, a tenant role string, or a JWT claim (stateless and unrevocable).
- Elevation = server-side session from password + TOTP; ~15 min idle and ~2 h absolute TTL; token stored hashed; cookie HttpOnly, SameSite=Strict, path-scoped. Reads need the session; mutations need a fresh single-use code plus a written reason.
- Content-blind by construction, not by application checks: a NOLOGIN DB role with column grants plus a permissive `TO <role> USING (true)` policy (permissive policies OR together; the policy opens rows, the column grant keeps content out).
- Append-only audit: insert+select grants, a trigger rejecting update/delete, a hash chain appended under an advisory lock, a verify endpoint.
- Provisioning only through a host CLI (shell access is the root of trust); no web path creates or promotes.
- Transparency: the reason for any action on a tenant is visible to that tenant; impersonation only as customer-approved, time-boxed access.
- Kill switches layer and fail closed (env → kill file → platform flag → org → user); an AI agent never inherits operator power (confused deputy).
- Verify a hand-rolled TOTP against the RFC 6238 Appendix B SHA-1 vectors (8 digits; derivable with Python stdlib `hmac` + `hashlib`).
