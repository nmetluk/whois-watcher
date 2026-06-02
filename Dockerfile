# syntax=docker/dockerfile:1.7

# =============================================================================
# Stage 1: builder — устанавливает зависимости через uv
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

# uv копируем из официального образа (быстрее curl-установщика, воспроизводимо)
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Только манифесты — слой кэшируется пока lock/pyproject не меняются
COPY pyproject.toml uv.lock ./

# --frozen: ровно версии из uv.lock; --no-dev: без dev-группы;
# --no-install-project: сам проект не ставить (аналог Poetry --no-root)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Код приложения — после deps, для лучшего кэша слоёв
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY scripts ./scripts

# =============================================================================
# Stage 2: runner — минимальный образ, только venv + код
# =============================================================================
FROM python:3.12-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
        ca-certificates \
        gnupg \
        wget \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --shell /bin/bash app

WORKDIR /app

# Целиком /app из builder: venv + код
COPY --from=builder --chown=app:app /app /app

USER app

# Healthcheck по умолчанию — пинг python; для бота переопределяется в compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

# По умолчанию — бот. Worker и scheduler переопределяют CMD в docker-compose.
CMD ["python", "-m", "src.main"]
