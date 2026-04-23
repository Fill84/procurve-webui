# syntax=docker/dockerfile:1.7
# Multi-stage build for procurve-webui:
#   1) frontend-build — builds the React SPA with Node 22 LTS.
#   2) backend        — installs the Python package (which also serves the SPA).

FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
# .npmrc is required: the project sets `legacy-peer-deps=true` to allow
# openapi-typescript@7 (peer: typescript@^5.x) to coexist with typescript@~6.0.2.
COPY frontend/package*.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS backend
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user + backups dir owned by it (compose will bind-mount host dir on top).
RUN adduser --system --group --no-create-home appuser \
    && mkdir -p /app/backups \
    && chown appuser:appuser /app/backups

# Copy backend sources needed by `pip install`. pyproject.toml declares
# `readme = "README.md"`, so the README must be present at install time.
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/README.md ./backend/README.md
COPY backend/procurve_client ./backend/procurve_client
COPY backend/app ./backend/app

RUN pip install /app/backend

# Pull in the built SPA from the first stage.
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Runtime entry + healthcheck scripts.
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/healthcheck.sh /app/healthcheck.sh
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh

USER appuser
EXPOSE 8080

# Healthcheck uses Python stdlib — avoids installing curl into the slim image.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD /app/healthcheck.sh

ENTRYPOINT ["/app/entrypoint.sh"]
