# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Cache mount persists pip's download cache across builds (BuildKit), so a
# requirements.txt change only re-downloads what actually changed instead of
# re-fetching everything (torch/sentence-transformers alone are ~1GB) —
# without --no-cache-dir, which would defeat the point of the mount.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
