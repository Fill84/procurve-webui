"""Tests for /api/v1/support.

The endpoint wraps `support_redirect`, which is a pure-info operation taking
no transport. Auth is still required (session dependency) for consistency
with the rest of the API.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_session
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.0.2.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    a = create_app()
    a.state.settings = settings
    return a


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_support_returns_info_when_authenticated(
    app: FastAPI, client: TestClient
) -> None:
    # Auth-gate is the only external dependency; a sentinel object satisfies it.
    app.dependency_overrides[get_session] = lambda: object()
    try:
        r = client.get("/api/v1/support")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["legacy_url"] == "http://www.procurve.com"
        assert body["current_url"] == "https://www.hpe.com/us/en/networking.html"
        assert body["available"] is False
        assert "procurve.com" in body["note"]
    finally:
        app.dependency_overrides.clear()


def test_support_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/support")
    assert r.status_code == 401
