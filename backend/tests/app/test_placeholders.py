"""Tests for Phase 3+ placeholder routers.

Each returns HTTP 501 with `{error: "not_implemented", phase: "3+"}`.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    return Settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.settings = settings
        yield c


EXPECTED = {"error": "not_implemented", "phase": "3+"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/configuration",
        "/api/v1/security",
        "/api/v1/diagnostics",
        "/api/v1/support",
    ],
)
def test_placeholder_returns_501(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 501
    assert r.json() == EXPECTED
