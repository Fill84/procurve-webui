"""Drift guard: the mock demo server must keep matching the real API shapes.

tools/mock_demo/demo_server.py hand-codes every response for screenshots and
hardware-free demos. Nothing used to validate those payloads, so backend
model changes silently broke the demo (the PortForm-backed port-edit modal
shipped a shape with zero overlapping keys for a while).

Rather than a hand-maintained model table, this test derives the contract
from the REAL app's route table: for every GET route the demo exposes, it
looks up the production route with the same path and validates the demo's
JSON against that route's declared ``response_model``. New demo endpoints
are therefore covered automatically as long as the real route declares a
response model.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import create_app

# Sample values for parameterized paths, and per-path query strings.
_PATH_PARAM_SAMPLES = {"port": "1", "idx": "1"}
_QUERY_OVERRIDES = {"/api/v1/status/alerts/{idx}": "?dt=11094915"}
# Paths that need on-disk state the demo doesn't ship (a stored backup file).
_SKIPPED = {"/api/v1/backups/{filename}/diff", "/api/v1/backups/{filename}/download"}


def _load_demo_app() -> Any:
    demo_path = (
        Path(__file__).resolve().parents[3] / "tools" / "mock_demo" / "demo_server.py"
    )
    spec = importlib.util.spec_from_file_location("demo_server", demo_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_server"] = module
    spec.loader.exec_module(module)
    return module.app


def _real_get_models() -> dict[str, Any]:
    """Map path -> declared response_model for the production app's GETs."""
    app = create_app()
    models: dict[str, Any] = {}
    for route in app.routes:
        if (
            isinstance(route, APIRoute)
            and "GET" in route.methods
            and route.response_model is not None
        ):
            models[route.path] = route.response_model
    return models


_REAL_MODELS = _real_get_models()
_DEMO_APP = _load_demo_app()


def _demo_get_paths() -> list[str]:
    return sorted(
        route.path
        for route in _DEMO_APP.routes
        if isinstance(route, APIRoute)
        and "GET" in route.methods
        and route.path.startswith("/api/")
        and route.path in _REAL_MODELS
        and route.path not in _SKIPPED
    )


def _resolve(path: str) -> str:
    concrete = path
    for name, value in _PATH_PARAM_SAMPLES.items():
        concrete = concrete.replace("{" + name + "}", value)
    return concrete + _QUERY_OVERRIDES.get(path, "")


@pytest.fixture(scope="module")
def demo_client() -> TestClient:
    client = TestClient(_DEMO_APP)
    # The demo issues a session cookie on login; whoami requires it.
    r = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert r.status_code == 200, r.text
    return client


def test_drift_guard_covers_a_meaningful_surface() -> None:
    """If this shrinks unexpectedly, the route matching itself broke."""
    assert len(_demo_get_paths()) >= 20, _demo_get_paths()


@pytest.mark.parametrize("path", _demo_get_paths())
def test_demo_response_matches_real_response_model(
    path: str, demo_client: TestClient
) -> None:
    r = demo_client.get(_resolve(path))
    assert r.status_code == 200, f"{path}: HTTP {r.status_code}: {r.text[:200]}"
    model = _REAL_MODELS[path]
    # TypeAdapter handles plain models and generics like list[BackupMeta].
    TypeAdapter(model).validate_python(r.json())
