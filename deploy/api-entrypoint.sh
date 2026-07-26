#!/usr/bin/env sh
# API container entrypoint: apply pending migrations, then serve.
# Idempotent — 'alembic upgrade head' is a no-op when already current — so it is
# safe on every deploy/restart and removes the manual migration step that made
# hand-run deploys fragile.
set -e

echo "[entrypoint] applying database migrations…"
alembic upgrade head

echo "[entrypoint] seeding demo user accounts…"
python -m app.platform.seed.demo_users || true

echo "[entrypoint] starting uvicorn…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
