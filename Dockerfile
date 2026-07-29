# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile — Amazon Media Plan Forecast Engine
#
# Multi-stage build:
#   Stage 1 (builder): install dependencies into a venv
#   Stage 2 (runtime): copy venv only — no build tools in the final image
#
# Base image: Red Hat UBI9 minimal Python 3.11 (IBM security policy compliant)
# Non-root user: appuser (uid 1001)
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM registry.redhat.io/ubi9/python-311-minimal:latest AS builder

WORKDIR /build

# Install build tools needed for native extensions (pyarrow, duckdb)
USER root
RUN microdnf install -y gcc gcc-c++ make && \
    microdnf clean all

COPY requirements.txt .

RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip --no-cache-dir && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM registry.redhat.io/ubi9/python-311-minimal:latest AS runtime

LABEL maintainer="Sumeet Mangotra <sumeet@example.com>"
LABEL description="Amazon Media Plan Forecast Engine"
LABEL version="2.0.0"

# Create non-root user (IBM security policy: never run as root)
RUN useradd -m -u 1001 -s /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=appuser:appuser . .

# Create temp directory with correct permissions
RUN mkdir -p /tmp/mediaplan && chown appuser:appuser /tmp/mediaplan

# Streamlit config
COPY --chown=appuser:appuser .streamlit/ .streamlit/

# Switch to non-root user
USER 1001

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Environment defaults (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TMP_DIR=/tmp/mediaplan \
    MAX_UPLOAD_MB=3072 \
    CHUNK_ROWS=300000 \
    DUCKDB_THREADS=4 \
    DUCKDB_MEMORY_LIMIT=4GB \
    LOG_LEVEL=WARNING

# Entry point
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.maxUploadSize=3072", \
     "--browser.gatherUsageStats=false"]
