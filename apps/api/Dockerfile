# EPISIGHT API image for hosted deploys (Render, Fly, Railway). Build context: apps/api.
# Applies migrations on start, then serves on $PORT. Seeding is a one-off step (docs/deployment.md).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so code changes reuse the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    EPISIGHT_ENV=prod \
    PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "episight db upgrade && exec uvicorn episight.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
