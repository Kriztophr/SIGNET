# Deployment — single VPS (Hostinger)

The whole stack runs on one VPS via Docker Compose: Caddy (edge, ports 80/443) →
FastAPI api container → Postgres, Redis, and a Celery worker. Nothing except Caddy
binds a host port; Postgres and Redis are reachable only on the internal Compose network.

The Caddy image is built from `deploy/Dockerfile.caddy`: it compiles the operations
console (React SPA in `frontend/`) and serves it at the domain root, proxying API paths
to the api container. `docker compose up -d --build` rebuilds it whenever the frontend
changes — no separate frontend deployment step exists.

## First deployment

1. **Provision** a VPS (4 GB RAM is sufficient for the MVP) running a recent Ubuntu LTS.
2. **Install Docker Engine + Compose plugin** (as root):
   ```sh
   curl -fsSL https://get.docker.com | sh
   ```
3. **Create a non-root deploy user** and add it to the `docker` group:
   ```sh
   adduser deploy && usermod -aG docker deploy
   ```
4. **Basic hardening** (before pointing DNS at the box):
   - SSH: key-only auth, disable root login (`/etc/ssh/sshd_config`).
   - Firewall: `ufw allow OpenSSH && ufw allow 80,443/tcp && ufw enable`.
   - Unattended security upgrades: `apt install unattended-upgrades`.
5. **Clone and configure** as the deploy user:
   ```sh
   git clone https://github.com/Kriztophr/NS.git icm-platform
   cd icm-platform
   cp .env.example .env
   # Edit .env:
   #   POSTGRES_PASSWORD  - strong and unique
   #   ICM_SECRET_KEY     - python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   #   ICM_ALLOWED_HOSTS  - your.real.domain (production refuses to boot with "*")
   #   DOMAIN             - your.real.domain (DNS A record must already point here)
   ```
   The api container **fails closed at startup** if the secret key is weak, debug is
   on, or the host allowlist is a wildcard — see [security.md](security.md).
6. **Start the stack**:
   ```sh
   docker compose up -d --build
   docker compose ps          # all services healthy
   curl -s https://your.real.domain/health
   ```
   Caddy obtains and renews the Let's Encrypt certificate automatically once DNS
   resolves to the VPS.
7. **Run migrations and create the first admin**:
   ```sh
   docker compose run --rm api alembic upgrade head
   docker compose run --rm \
     -e ICM_BOOTSTRAP_ADMIN_EMAIL=you@example.com \
     -e ICM_BOOTSTRAP_ADMIN_PASSWORD='a-strong-password' \
     api python -m app.platform.auth.bootstrap
   ```

## Updating

```sh
git pull
docker compose up -d --build   # rebuilds changed images, restarts only affected services
docker compose ps
```

Migrations apply automatically when the api container starts
(`deploy/api-entrypoint.sh` runs `alembic upgrade head`, a no-op when already
current), so a normal `docker compose up -d --build` migrates and serves in one
step. To run them manually anyway: `docker compose run --rm api alembic upgrade head`.

## Deploying with Coolify (recommended for this VPS)

This VPS runs Coolify, which is purpose-built to own deploys, TLS, secrets, and
logs — replacing the manual git-bundle-over-SSH pipeline. To migrate:

1. Reach the Coolify dashboard: `ssh -L 8000:localhost:8000 root@<vps>` then open
   `http://localhost:8000` (its port is firewalled off the public internet).
2. Add this GitHub repository as a **Docker Compose** resource; set the compose
   path to `docker-compose.coolify-managed.yml`.
3. Set environment variables in the Coolify UI: `POSTGRES_PASSWORD`,
   `ICM_SECRET_KEY` (48+ random chars), and `ICM_ALLOWED_HOSTS` (your FQDN plus
   `127.0.0.1`). Assign the domain to the `caddy` service — Coolify exposes it as
   the `SERVICE_FQDN_CADDY_80` magic variable and generates the Traefik route to
   port 80 (the `_80` suffix is required: the caddy image exposes 80 and 443, so
   without it Coolify cannot tell which port to route to).
4. Deploy, then enable **auto-deploy on push** so every push to `main` redeploys.
5. Bootstrap the first admin once (Coolify terminal → the api container):
   `ICM_BOOTSTRAP_ADMIN_EMAIL=you@example.com ICM_BOOTSTRAP_ADMIN_PASSWORD=… python -m app.platform.auth.bootstrap`.

Coolify manages its own Traefik, so the `docker-compose.coolify.yml` Traefik-label
overlay is only needed for the manual (non-Coolify) deployment path.

## Backups

- **Postgres** — nightly logical dump, kept off the VPS:
  ```sh
  docker compose exec -T postgres pg_dump -U icm icm | gzip > backup-$(date +%F).sql.gz
  ```
  Schedule via cron and sync to object storage or another machine. Test restores
  periodically: `gunzip -c backup.sql.gz | docker compose exec -T postgres psql -U icm icm`.
- **Volumes** — `pgdata` is the source of truth; `redisdata` is expendable (broker
  state only); `caddy_data` holds TLS certificates and is cheap to keep.
- **Artifacts/object storage** — when S3-compatible storage lands, backups follow the
  provider's versioning; nothing extra on the VPS.

## Logs and health

- `docker compose logs -f api worker` — structured app logs go to stdout (JSON in
  production). Failed logins and throttle events appear as `security` log events.
- `GET /health` — liveness for the api; Compose healthchecks cover postgres, redis,
  api, and the Celery worker.
- Every response carries `X-Correlation-ID`; pass one in to trace a request across
  logs and audit events (`GET /governance/audit-events`, auditor/admin).

## Security

The full security model — authentication, RBAC, tenant isolation, fail-closed
gates, throttling, headers, secrets hygiene, and known limitations — is documented
in [security.md](security.md). CI runs lint + tests on every push
(`.github/workflows/ci.yml`); re-run the dependency CVE audit periodically as
described there.

## Future local GPU node (extension point — do not build yet)

The Celery broker is the seam: a worker on the RTX 4060 machine will join by pointing
at the VPS Redis over a private tunnel (WireGuard or SSH) and subscribing to a dedicated
queue (e.g. `gpu`). Nothing in the current stack assumes workers are local, so no
changes to the VPS topology will be needed beyond exposing Redis through the tunnel.
