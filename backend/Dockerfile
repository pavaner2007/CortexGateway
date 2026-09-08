# ─────────────────────────────────────────────────────────────────────────────
# Cortex Gateway — Backend Dockerfile
# Multi-stage build: builder + slim runtime image.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS builder

# Install build tools needed for asyncpg (C extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS runtime

# Non-root user for security
RUN addgroup --system cortex && adduser --system --ingroup cortex cortex

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Owned by non-root user
RUN chown -R cortex:cortex /app
USER cortex

# Environment defaults (overridden by docker-compose or runtime env)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
