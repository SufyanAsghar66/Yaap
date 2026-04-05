# ─── YAAP Backend Dockerfile ──────────────────────────────────────────────────
# Multi-stage build: builder installs deps, final image is lean production image.

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for psycopg2, Pillow, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential      \
    libpq-dev            \
    libjpeg-dev          \
    zlib1g-dev           \
    libwebp-dev          \
    libffi-dev           \
    libssl-dev           \
    curl                 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into /build/wheels
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="YAAP Engineering <eng@yaap.app>"
LABEL description="YAAP Django Backend — Real-time AI voice translation"

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5              \
    libjpeg62-turbo     \
    curl                \
    && rm -rf /var/lib/apt/lists/*

# Create non-root app user
RUN groupadd -r yaap && useradd -r -g yaap -d /app yaap

WORKDIR /app

# Install wheels from builder stage (no internet needed)
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Copy project source
COPY --chown=yaap:yaap . .

# Create directories for static/media
RUN mkdir -p /app/staticfiles /app/media && chown -R yaap:yaap /app

# Switch to non-root user
USER yaap

# Django checks
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=yaap.settings

EXPOSE 8000

# Health check (container level)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command (overridden by docker-compose)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "yaap.asgi:application"]
