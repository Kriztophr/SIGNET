# Deployment — single VPS (Hostinger)

The whole stack runs on one VPS via Docker Compose: Caddy (edge, ports 80/443) →
FastAPI api container → Postgres, Redis, and a Celery worker. Nothing except Caddy
binds a host port; Postgres and Redis are reachable only on the internal Compose network.

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

Run database migrations before restarting the api:
`docker compose run --rm api alembic upgrade head`.

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
