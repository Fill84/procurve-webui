"""Tests for the same-origin write enforcement (app/csrf.py).

SameSite=Strict already blocks cross-*site* forgery; this middleware closes
the same-site/different-port gap (e.g. a dev server on localhost:3000
riding the cookie against localhost:8080).
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.csrf import origin_matches_host
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SWITCH_HOST", "192.0.2.3")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    app = create_app()
    with TestClient(app) as c:
        app.state.settings = Settings()
        yield c


# ---------------------------------------------------------------------------
# Unit: origin/host matching rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "host", "expected"),
    [
        (None, "localhost:8080", True),  # non-browser client — allowed
        ("http://localhost:8080", "localhost:8080", True),
        ("http://localhost:3000", "localhost:8080", False),  # same-site, wrong port
        ("http://evil.example", "localhost:8080", False),
        ("null", "localhost:8080", False),  # sandboxed iframe / data: page
        ("http://localhost", "localhost:80", True),  # implicit default port
        ("http://LOCALHOST:8080", "localhost:8080", True),  # case-insensitive
        ("http://localhost:8080", None, False),
        ("http://localhost:8080", "", False),
    ],
)
def test_origin_matches_host(origin: str | None, host: str | None, expected: bool) -> None:
    assert origin_matches_host(origin, host) is expected


# ---------------------------------------------------------------------------
# Integration: middleware behavior
# ---------------------------------------------------------------------------


def test_cross_origin_write_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": ""},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code == 403
    assert r.json()["error"] == "csrf"


def test_same_origin_write_passes_middleware(client: TestClient) -> None:
    """Matching Origin must pass the CSRF layer (the request then proceeds
    to the actual handler — here login, which will fail further down for
    other reasons in this fixture, but NOT with the csrf error)."""
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": ""},
        headers={"Origin": f"http://{client.base_url.netloc.decode()}"},
    )
    assert not (r.status_code == 403 and r.json().get("error") == "csrf")


def test_originless_write_passes_middleware(client: TestClient) -> None:
    """curl-style clients (no Origin header) are not CSRF vectors."""
    r = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert not (r.status_code == 403 and r.json().get("error") == "csrf")


def test_cross_origin_get_is_not_blocked(client: TestClient) -> None:
    """Reads are not gated — CSRF is a state-change concern; GETs stay open."""
    r = client.get(
        "/api/v1/health/live", headers={"Origin": "http://localhost:3000"}
    )
    assert r.status_code == 200
