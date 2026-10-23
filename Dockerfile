FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .

RUN pip install --no-cache-dir torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# ---- final: just the venv + app code, no build toolchain ----
FROM python:3.11-slim

# libgomp1: OpenMP runtime torch's CPU backend needs, not included on a bare slim image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY api.py ./
COPY src/ ./src/

# Default, no-mounted-disk location for uploads (see api.py's UPLOAD_DIR env
# override) and jobs.db (src/store.py's JOBS_DB_PATH) -- both are lost on
# container restart/replacement unless a persistent volume is mounted over
# them. On Render specifically: a Disk can only be mounted at one path, so
# point both env vars under it instead, e.g. mount a Disk at /app/data and
# set UPLOAD_DIR=/app/data/uploads, JOBS_DB_PATH=/app/data/jobs.db.
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

USER appuser

# GOOGLE_API_KEY (or GEMINI_API_KEY, mapped to it at startup -- see api.py)
# must be provided at run time, e.g. `docker run -e GEMINI_API_KEY=... ` or
# your platform's env var settings. Never baked into the image.
#
# API_KEY (src/auth.py): the shared key clients must send back as either an
# `X-API-Key` header or `?api_key=` query param. Set this in any deployment
# reachable outside your own machine -- leaving it unset disables auth
# entirely.
#
# CORS_ORIGINS (api.py): comma-separated allowlist of frontend origins
# allowed to call this API. Defaults to the Vite dev server's own origins --
# set this to the deployed frontend's real origin, or every request from it
# gets rejected by CORS.

EXPOSE 8000

# $PORT: Render (and most PaaS Docker runners) assign the container a port
# at runtime via this env var rather than always using the one declared by
# EXPOSE -- falls back to 8000 for a plain `docker run` with no PORT set.
# Shell-form CMD (not exec-form/JSON array) is required here so $PORT
# actually expands; it's the one place in this file that needs to.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 8000)}/health', timeout=3)" || exit 1

# Single worker, intentionally: the job store (src/store.py) is a local
# SQLite file, not a service multiple processes can share concurrently --
# do not add --workers or run more than one replica until that's replaced
# with a shared store (Redis/Postgres). See ARCHITECTURE.md's known limitations.
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
