#!/usr/bin/env bash
# Generate TypeScript types from the backend OpenAPI schema.
#
# Preferred path: run the Python dump script, which constructs the FastAPI app
# in-process and writes openapi.json without starting a server.
# Fallback: curl a running backend on :8080 if the Python dump fails (e.g. the
# backend venv is not active in the current shell).
set -euo pipefail

cd "$(dirname "$0")/.."

if python scripts/dump-openapi.py 2>/dev/null; then
  echo "[gen-api] OpenAPI dumped via Python"
else
  echo "[gen-api] Python dump failed - falling back to HTTP curl" >&2
  curl -fsS http://127.0.0.1:8080/openapi.json -o openapi.json
fi

npx openapi-typescript openapi.json -o src/api/schema.d.ts
echo "[gen-api] Generated src/api/schema.d.ts"
