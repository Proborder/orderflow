# --- STAGE 1: Builder ---
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=2.3.2 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-root --no-ansi

# --- STAGE 2: Runtime ---
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY payment-service/ /app/payment-service/

ENV PYTHONPATH=/app/payment-service

WORKDIR /app/payment-service

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
