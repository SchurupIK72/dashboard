FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --system dashboard \
    && useradd --system --gid dashboard --home-dir /app dashboard \
    && mkdir -p /app/data \
    && chown -R dashboard:dashboard /app

COPY --chown=dashboard:dashboard pyproject.toml uv.lock ./
USER dashboard
RUN uv sync --frozen --no-dev

COPY --chown=dashboard:dashboard src ./src

EXPOSE 8000

CMD ["uvicorn", "dashboard.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
