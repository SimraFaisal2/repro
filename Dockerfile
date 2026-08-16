# syntax=docker/dockerfile:1

# ── Stage 1: build the React dashboard ──────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: runtime (backend + served frontend) ────────────────────
FROM python:3.12-slim
WORKDIR /app

# git is used by repo cloning and patch application
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend /build/frontend/dist frontend/dist

ENV PYTHONPATH=/app/backend
ENV REPRO_DATA_DIR=/app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["python", "backend/run.py"]
