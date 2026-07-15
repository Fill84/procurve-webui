"""Tests for /api/v1/health.

The health endpoint uses a one-shot fresh transport (no session required),
so we use respx to mock the HTTP call against the switch directly.
"""
from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

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
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.settings = settings
        yield c


@respx.mock
def test_health_ok_when_switch_responds_200(client: TestClient) -> None:
    route = respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>"),
    )
    r = client.get("/api/v1/health")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok", "switch_reachable": True}
    assert route.called


@respx.mock
def test_health_503_when_transport_fails(client: TestClient) -> None:
    respx.get("http://192.0.2.3/home.html").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )
    r = client.get("/api/v1/health")
    assert r.status_code == 503
    assert r.json() == {"status": "unreachable", "switch_reachable": False}


@respx.mock
def test_health_503_when_switch_returns_non_200(client: TestClient) -> None:
    respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(500, text="internal error"),
    )
    r = client.get("/api/v1/health")
    assert r.status_code == 503
    assert r.json() == {"status": "unreachable", "switch_reachable": False}


def test_health_does_not_require_auth(client: TestClient) -> None:
    """Health must be callable without a session cookie — it's for monitoring."""
    with respx.mock:
        respx.get("http://192.0.2.3/home.html").mock(
            return_value=Response(200, text="<html>ok</html>"),
        )
        # No login call performed; no cookie set.
        r = client.get("/api/v1/health")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Switch-safety: liveness never probes the switch; reachability is cached.
# ---------------------------------------------------------------------------


@respx.mock
def test_liveness_never_contacts_switch(client: TestClient) -> None:
    """/health/live is the Docker HEALTHCHECK target — zero switch traffic."""
    route = respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>"),
    )
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert route.called is False


@respx.mock
def test_health_probe_is_cached_within_ttl(client: TestClient) -> None:
    """Repeated /health calls inside the TTL cost exactly one switch probe."""
    route = respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>"),
    )
    for _ in range(5):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
    assert route.call_count == 1


@respx.mock
def test_health_failure_is_cached_too(client: TestClient) -> None:
    """An unreachable verdict is also served from cache — no retry storm."""
    route = respx.get("http://192.0.2.3/home.html").mock(
        side_effect=httpx.ConnectError("connection refused"),
    )
    for _ in range(4):
        r = client.get("/api/v1/health")
        assert r.status_code == 503
    assert route.call_count == 1
