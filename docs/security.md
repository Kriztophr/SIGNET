# Security model

This document describes the platform's security controls, per master spec §23
("Security and isolation") and §5.6 ("Fail closed on consequential ambiguity").

## Authentication and sessions

- **JWT bearer tokens** (HS256) issued by `POST /auth/login`; 60-minute expiry by
  default (`ICM_ACCESS_TOKEN_EXPIRE_MINUTES`). Tokens carry `iss`, `sub`, `tenant_id`,
  `role`, `iat`, `exp`; decoding **requires** `exp`, `iss`, and `sub` and verifies the
  issuer — a token missing claims or signed with any other key is rejected.
- **Privileges are never read from the token.** The role and active flag are loaded
  from the database on every request, so deactivating a user or changing a role takes
  effect immediately regardless of outstanding tokens.
- **Passwords**: bcrypt with per-hash salts; minimum 12 characters enforced at user
  creation; 72-byte bcrypt bound enforced rather than silently truncated; unknown-user
  logins verify against a dummy hash so response timing does not reveal account
  existence.
- **Login throttling**: after `ICM_LOGIN_MAX_FAILURES` (default 5) failed attempts for
  an account within `ICM_LOGIN_WINDOW_SECONDS` (default 900), further logins return
  429 — including with the correct password — until the window passes. A successful
  login resets the window. The window store is in-process, which is correct for the
  single-API-container deployment; scale-out requires moving it to Redis behind the
  same interface (`app/platform/auth/throttle.py`).
- Login successes and failures are emitted as structured `security` log events.

## Authorization

- Roles per spec §20 (`admin`, `operator`, `reviewer`, `evaluator`, `auditor`,
  `environment_manager`, `resilience_manager`), enforced by `require_roles(...)` on
  every mutating route; `admin` always passes.
- A second, service-level check guards review decisions: the task's `eligible_role`
  must match the caller (so a reviewer cannot decide an escalated admin-only task
  even though the route admits reviewers).
- The audit stream is readable only by `auditor`/`admin`.
- The test suite sweeps **every registered route** and asserts that only `/health`
  and `/auth/login` answer without a token (`tests/test_security.py`).

## Tenant isolation

- Every tenant-owned table carries `tenant_id` (and optional `project_id`); child
  tables scope through joins to their owning parent.
- All repository lookups filter by the caller's tenant; a cross-tenant hit is
  indistinguishable from a miss (404). Covered by per-module isolation tests.
- Artifact and workspace storage is only reachable through tenant-scoped repository
  lookups; storage keys never appear in API responses, and the local storage backend
  rejects path traversal.

## Fail-closed controls

- Stage completion is blocked until every contracted output exists.
- Review and eval gates pause runs; nothing advances without an explicit decision.
- Regression packs count missing evidence as failure; promotions block on any
  missing, failed, or regressed evidence and re-check at approval time.
- Resilience thresholds with no supporting evidence are breaches, not skips.
- **Production boot refuses insecure configuration**: default/short `ICM_SECRET_KEY`,
  `ICM_DEBUG=true`, or `ICM_ALLOWED_HOSTS=*` abort startup
  (`validate_production_settings`).

## Transport and edge

- Caddy is the only host-exposed service (80/443) with automatic TLS; Postgres,
  Redis, and the API live on the internal Compose network only.
- Request bodies are capped at 10 MB at the edge.
- Security headers are set **both** at the edge and by app middleware
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Cross-Origin-Opener-Policy`); the app additionally enforces a Host-header
  allowlist (`ICM_ALLOWED_HOSTS`).
- Interactive API docs and the OpenAPI schema are disabled in production.
- No CORS middleware is registered: browsers cannot make cross-origin calls unless
  a deployment explicitly opts in.

## Secrets and evidence hygiene

- All secrets arrive via environment variables; `.env` is git-ignored and never
  baked into images. Generate the secret key with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Audit payloads and context manifests contain identifiers, rationales, and metric
  values — never credentials or tokens.
- Containers run as a non-root user on a minimal base image; the app filesystem is
  owned by that user; dependency installs are lockfile-frozen (`uv sync --frozen`).

## Supply chain and CI

- Dependencies are pinned via `uv.lock`; `pip-audit` against the exported production
  requirements reports no known vulnerabilities as of 2026-07-05 — re-run
  periodically:
  `uv export --frozen --no-dev --format requirements-txt -o reqs.txt && uvx pip-audit -r reqs.txt --disable-pip`
- GitHub Actions CI (`.github/workflows/ci.yml`) runs lint, format check, and the
  full test suite on every push and pull request.

## Host firewall on Docker hosts (important gotcha)

Docker-published container ports **bypass ufw** — Docker inserts its own iptables
rules ahead of ufw's, so `ufw deny` has no effect on them. Blocking a published
port from the internet requires rules in the `DOCKER-USER` chain, matching the
original (pre-DNAT) destination port. The production VPS applies this pattern in
`/etc/ufw/after.rules` (marker block `ICM DOCKER-USER HARDENING`): host rules
allow rate-limited 22 plus 80/443, and `DOCKER-USER` drops internet traffic to
Coolify (8000), Traefik's admin port (8080), and Coolify realtime (6001–6002).
Reach the Coolify UI through an SSH tunnel instead:
`ssh -L 8000:localhost:8000 root@<vps>` → `http://localhost:8000`.

Database backups: `/etc/cron.d/icm-backup` runs `pg_dump` nightly at 03:15 to
`/var/backups/icm/` with 14-day retention (`/usr/local/bin/icm-backup.sh`),
alongside Hostinger's weekly whole-VPS backups.

## Known limitations (documented, not hidden)

- Login throttling is per-process (see above).
- Concurrent reviewer-score submissions rely on in-transaction status checks;
  `SELECT ... FOR UPDATE` row locking is planned alongside the Celery execution
  phase (spec §26).
- There is no token revocation list; deactivating the user (`is_active=false`)
  is the immediate kill switch, and token lifetime is short.
- Redis and Postgres rely on network isolation rather than in-network
  authentication; both are unreachable from outside the Compose network.
