"""Regression guards: the Phase 2 placeholders are gone.

All 4 placeholder tabs (configuration / security / diagnostics / support)
now have real routers. This file exists to pin that down — if somebody
reintroduces a 501 "not_implemented" response on one of these paths the
CI should fail.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

_PHASE2_PLACEHOLDER_BODY = {"error": "not_implemented", "phase": "3+"}


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


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/configuration",
        "/api/v1/security",
        "/api/v1/diagnostics",
        "/api/v1/support",
    ],
)
def test_formerly_placeholder_path_is_no_longer_501(
    client: TestClient, path: str
) -> None:
    """None of the four formerly-placeholder tabs may return the 501
    not_implemented body anymore. They either expose real sub-endpoints
    (404 on the bare prefix is fine) or require auth (401). 501 with the
    Phase 2 marker is forbidden.
    """
    r = client.get(path)
    assert r.status_code != 501, r.text
    try:
        body = r.json()
    except ValueError:
        body = {}
    assert body != _PHASE2_PLACEHOLDER_BODY
