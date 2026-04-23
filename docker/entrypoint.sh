#!/bin/sh
set -e

: "${SWITCH_HOST:?SWITCH_HOST must be set}"
: "${SESSION_SECRET:?SESSION_SECRET must be set (generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\")}"

exec uvicorn app.main:app \
    --app-dir /app/backend \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8080}"
