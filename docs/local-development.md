# Local development

Two ways to run Signet on a workstation. Use Compose when you want parity with
production; use the SQLite path when Docker isn't available (or you just want the
console up in a minute to look at a UI change).

## Option A — Docker Compose (production parity)

Closest to the deployed stack: Postgres, Redis, a Celery worker, and Caddy.

```sh
docker compose up --build
```

Then apply migrations and create an admin (see [deployment.md](deployment.md)).
This is the only local option where **agent execution actually runs**, because it
is the only one with a Celery worker and broker.

## Option B — SQLite, no Docker

The API and console run directly against a SQLite file. The test suite already
runs on SQLite, and the full migration chain applies cleanly to it, so this is a
real instance rather than a mock — it simply has no Postgres, no Redis, and no
worker.

**What this path cannot do:** automated (agent) stages have no worker to execute
them, so they degrade to manual completion with an `error_summary` — which is the
designed behavior, and a decent demonstration of it. Everything else (workflows,
gates, reviews, evals, promotions, evidence packs) works normally.

Keep the database and object storage outside the repo so a stray `git add` can't
sweep them in. Adjust the paths below to taste.

```powershell
# PowerShell — one shell, since env vars must be set for every command
$env:ICM_DATABASE_URL = "sqlite:///C:/dev-data/signet-local.db"
$env:ICM_STORAGE_ROOT = "C:/dev-data/signet-storage"
$env:ICM_ALLOWED_HOSTS = "localhost,127.0.0.1"

# First run only: schema, admin, demo content
.venv/Scripts/python.exe -m alembic upgrade head

$env:ICM_BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"
$env:ICM_BOOTSTRAP_ADMIN_PASSWORD = "<12+ characters>"
.venv/Scripts/python.exe -m app.platform.auth.bootstrap

# Optional: the four enterprise scenario packs (workflows, rubrics, eval suites)
$env:ICM_SEED_ADMIN_EMAIL = "admin@example.com"
.venv/Scripts/python.exe -m app.platform.seed.usecases

# Optional: one account per role, for exercising RBAC in the console
$env:ICM_SEED_DEMO_USERS = "1"
$env:ICM_DEMO_USERS_PASSWORD = "<12+ characters>"
.venv/Scripts/python.exe -m app.platform.seed.demo_users

# Serve (two terminals, or background the first)
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend; npm run dev
```

Equivalent on macOS/Linux with `export` and `.venv/bin/python`.

| What | Where |
|---|---|
| Console | http://localhost:5173 |
| API | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

The console's dev server proxies API paths to `:8000` (see
`frontend/vite.config.ts`), so the app always calls same-origin URLs and needs no
CORS — the same arrangement Caddy provides in production.

### Gotchas

- **Run uvicorn with `--reload`.** Without it, code changes (a new route in
  particular) are invisible until you restart, and the symptom is a confusing
  404 on an endpoint you can see in the source.
- **`ICM_SEED_ADMIN_EMAIL`** must name an existing admin or the use-case seeder
  refuses to run; it defaults to a specific address that won't exist locally.
- **Demo accounts use `demo-*@example.com`**, not `.local` — Pydantic's
  `EmailStr` rejects reserved domains like `.local`, so such an account can be
  created but can never log in.
- **Env vars don't persist between shells.** Set them in the same session you run
  commands from, or put them in a gitignored `.env`.
- Forgot the local password? Same recovery path as production — see
  "Account recovery" in [deployment.md](deployment.md).

## Running the tests

Tests are hermetic (in-memory SQLite, temp storage) and need no services or env
vars:

```sh
uv run pytest              # or: .venv/Scripts/python.exe -m pytest
uv run ruff check .
uv run ruff format --check .
```

After changing tests, regenerate the plain-language catalogue reviewers read:

```sh
python tools/generate_test_catalog.py     # writes docs/test-catalog.md
```
