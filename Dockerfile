# syntax=docker/dockerfile:1

# ---------- Stage 1: build the virtual environment ----------
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

# Compile .pyc files at build time, copy (not link) files, and use the image's Python.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# 1) Dependencies only. This layer is reused until pyproject.toml or uv.lock change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# 2) Your code. Changes often, so it comes last.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# ---------- Stage 2: the small image that actually runs ----------
FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app
WORKDIR /app

# Only what the app needs at runtime: the venv, migrations, scripts and seed data.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app data ./data

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000

# Hosts like Render pass the port in $PORT; locally it defaults to 8000.
CMD ["sh", "-c", "exec uvicorn rti_mate.api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
