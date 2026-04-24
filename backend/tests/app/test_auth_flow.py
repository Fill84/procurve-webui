"""Integration tests for Task 2.2 — session auth + transport cache.

These tests use respx to mock the switch credential probe (`GET /home.html`).
They never talk to a real switch.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from app import auth as auth_module
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
        # lifespan already constructed settings from the test env; override to
        # make sure any future drift between here and lifespan is harmless.
        app.state.settings = settings
        yield c


def _mock_probe_ok() -> respx.Route:
    return respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>"),
    )


def _mock_probe_unauthorized() -> respx.Route:
    return respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(401, text="unauthorized"),
    )


@respx.mock
def test_login_with_blank_creds_succeeds_when_switch_accepts_blank(
    client: TestClient,
) -> None:
    route = _mock_probe_ok()
    resp = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "session_id" in body
    assert "expires_at" in body
    assert route.called
    # Cookie set
    assert "session" in resp.cookies


@respx.mock
def test_login_with_wrong_creds_returns_401(client: TestClient) -> None:
    _mock_probe_unauthorized()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "bogus"},
    )
    assert resp.status_code == 401
    assert "session" not in resp.cookies


@respx.mock
def test_logout_clears_session(client: TestClient) -> None:
    _mock_probe_ok()
    login = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert login.status_code == 200
    # Confirm session works
    who = client.get("/api/v1/auth/whoami")
    assert who.status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    # Subsequent whoami is unauthorized.
    # TestClient preserves cookies but the server-side store is cleared.
    who2 = client.get("/api/v1/auth/whoami")
    assert who2.status_code == 401


@respx.mock
def test_whoami_returns_username_when_authenticated(client: TestClient) -> None:
    _mock_probe_ok()
    client.post("/api/v1/auth/login", json={"username": "operator", "password": "pw"})
    resp = client.get("/api/v1/auth/whoami")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "operator"
    assert "expires_at" in body


def test_whoami_401_when_no_cookie(client: TestClient) -> None:
    # No login performed; no cookie set.
    resp = client.get("/api/v1/auth/whoami")
    assert resp.status_code == 401


@respx.mock
def test_session_expires_after_ttl(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_probe_ok()
    t0 = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(auth_module, "_now", lambda: t0)
    login = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert login.status_code == 200
    # Within TTL — ok.
    monkeypatch.setattr(auth_module, "_now", lambda: t0 + timedelta(hours=1))
    assert client.get("/api/v1/auth/whoami").status_code == 200
    # After TTL — expired.
    monkeypatch.setattr(auth_module, "_now", lambda: t0 + timedelta(hours=9))
    assert client.get("/api/v1/auth/whoami").status_code == 401
