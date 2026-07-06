FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY deploy/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh

RUN chmod +x /usr/local/bin/api-entrypoint.sh \
    && mkdir -p /app/data \
    && groupadd -r icm && useradd -r -g icm -d /app icm && chown -R icm:icm /app
USER icm

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# The API applies migrations on boot; the Celery worker overrides this command.
CMD ["api-entrypoint.sh"]
