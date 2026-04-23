"""Dump the backend's OpenAPI schema to frontend/openapi.json without serving.

Usage (from frontend/):
    python scripts/dump-openapi.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure the backend package is importable.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Settings requires SWITCH_HOST and SESSION_SECRET. Set dummy values just to
# construct the app; openapi() does not touch the switch or real session store.
os.environ.setdefault("SWITCH_HOST", "127.0.0.1")
os.environ.setdefault("SESSION_SECRET", "x" * 32)

from app.main import create_app  # noqa: E402

app = create_app()
openapi = app.openapi()

out = Path(__file__).resolve().parents[1] / "openapi.json"
out.write_text(json.dumps(openapi, indent=2), encoding="utf-8")
print(f"Wrote {out}")
