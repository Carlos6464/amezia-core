FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.25 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --locked --no-dev

COPY apps/api/ .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["arq", "src.infrastructure.queue.worker.WorkerSettings"]
