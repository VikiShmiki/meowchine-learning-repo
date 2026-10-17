FROM ghcr.io/astral-sh/uv:0.12.17 AS uv

FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable
RUN --mount=type=cache,target=/root/.cache/huggingface \
    uv run --no-sync python -c "from pathlib import Path; from smart_recycling.minilm import cache_encoder; cache_encoder(Path('/app/runtime-models/all-MiniLM-L6-v2'))"

RUN --mount=type=cache,target=/root/.cache/huggingface \
    uv run --no-sync python -c "from pathlib import Path; from smart_recycling.multilingual import cache_encoder; cache_encoder(Path('/app/runtime-models/multilingual-minilm'))"

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SRA_MINILM_MODEL_PATH="/app/runtime-models/all-MiniLM-L6-v2" \
    SRA_MULTILINGUAL_MODEL_PATH="/app/runtime-models/multilingual-minilm"

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/runtime-models /app/runtime-models
COPY artifacts/models/ml_v3_audit ./artifacts/models/ml_v3_audit
COPY data/seed ./data/seed
COPY data/infrastructure ./data/infrastructure
COPY data/policy ./data/policy
COPY data/classifier ./data/classifier
COPY data/coverage ./data/coverage
COPY data/upgrades ./data/upgrades
COPY data/parking ./data/parking
COPY web ./web

RUN groupadd --system app && useradd --system --gid app --home /app --no-create-home app \
    && mkdir -p /app/runtime && chown app:app /app/runtime \
    && chmod -R a+rX /app/runtime-models
USER app

RUN python -c "from pathlib import Path; from smart_recycling.minilm import load_encoder; from smart_recycling.multilingual import load_encoder as load_multilingual; load_encoder(Path('/app/runtime-models/all-MiniLM-L6-v2')); load_multilingual(Path('/app/runtime-models/multilingual-minilm'))"

EXPOSE 8000
CMD ["uvicorn", "smart_recycling.api:app", "--host", "0.0.0.0", "--port", "8000"]
