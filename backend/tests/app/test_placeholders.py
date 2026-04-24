"""Tests for Phase 3+ placeholder routers.

Each remaining placeholder returns HTTP 501 with
``{error: "not_implemented", phase: "3+"}``.

Task 3.5a replaced the ``/api/v1/configuration`` placeholder with a real
router, so the parametrize list is currently empty.  Future Phase 3+ work
may re-populate this (unlikely — all remaining tabs already have real
routers), in which case the parametrize list comes back to life.  Keeping
the file alive (rather than deleting it outright) preserves the symmetry
with ``placeholders.py``.
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

# Remaining placeholder GET endpoints (empty: all tabs now have real routers).
PLACEHOLDER_PATHS: list[str] = []


@pytest.mark.skipif(
    not PLACEHOLDER_PATHS, reason="no placeholder endpoints remain"
)
@pytest.mark.parametrize("path", PLACEHOLDER_PATHS or ["__never__"])
def test_placeholder_returns_501(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 501
    assert r.json() == EXPECTED


def test_configuration_is_no_longer_a_placeholder(client: TestClient) -> None:
    """Regression guard: a plain GET to /api/v1/configuration must not
    return the 501 placeholder shape anymore.

    The real configuration router does NOT expose ``GET /``; the
    sub-tab endpoints live at ``/api/v1/configuration/system``,
    ``/.../ip``, etc. So this URL now returns 404 (no route), 401 (if
    auth kicks in first), or another real status — just not 501.
    """
    r = client.get("/api/v1/configuration")
    assert r.status_code != 501, r.text
    body: object
    try:
        body = r.json()
    except ValueError:
        body = {}
    assert body != EXPECTED
