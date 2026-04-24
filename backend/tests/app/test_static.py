"""Tests for the SPA static-file mount (Task 2.6).

The mount is only active when the `dist_dir` exists; tests pass a
`tmp_path`-backed fake to `create_app(dist_dir=...)` to exercise it.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.0.2.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    return Settings()


def _build_fake_dist(root: Path) -> Path:
    """Create a minimal dist/ tree: index.html + assets/foo.js."""
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><body>spa</body></html>",
        encoding="utf-8",
    )
    (dist / "assets" / "foo.js").write_text(
        "console.log('hello');",
        encoding="utf-8",
    )
    return dist


@pytest.fixture
def client_with_dist(
    settings: Settings, tmp_path: Path
) -> Iterator[tuple[TestClient, Path]]:
    dist = _build_fake_dist(tmp_path)
    app = create_app(dist_dir=dist)
    with TestClient(app) as c:
        app.state.settings = settings
        yield c, dist


def test_static_mount_skipped_when_dist_missing(
    settings: Settings, tmp_path: Path
) -> None:
    """If the dist dir does not exist, the mount is a no-op and startup
    still succeeds. Root `/` should 404 (no fallback installed)."""
    missing = tmp_path / "does-not-exist"
    assert not missing.exists()
    app = create_app(dist_dir=missing)
    with TestClient(app) as c:
        app.state.settings = settings
        r = c.get("/")
        assert r.status_code == 404


def test_static_serves_index_html_for_root(
    client_with_dist: tuple[TestClient, Path],
) -> None:
    client, _dist = client_with_dist
    r = client.get("/")
    assert r.status_code == 200
    assert "<body>spa</body>" in r.text


def test_static_serves_assets(
    client_with_dist: tuple[TestClient, Path],
) -> None:
    client, _dist = client_with_dist
    r = client.get("/assets/foo.js")
    assert r.status_code == 200
    assert r.text == "console.log('hello');"


def test_static_spa_fallback_for_unknown_path(
    client_with_dist: tuple[TestClient, Path],
) -> None:
    """Client-routed paths like /status/ports/1 must fall through to index.html."""
    client, _dist = client_with_dist
    r = client.get("/status/ports/1")
    assert r.status_code == 200
    assert "<body>spa</body>" in r.text


def test_api_routes_not_shadowed_by_spa_fallback(
    client_with_dist: tuple[TestClient, Path],
) -> None:
    """The SPA catch-all MUST be registered after /api/v1/* — verify that
    an unauthenticated whoami still returns JSON 401, not index.html."""
    client, _dist = client_with_dist
    r = client.get("/api/v1/auth/whoami")
    assert r.status_code == 401
    # JSON body, not HTML.
    assert "body" not in r.text
    assert r.headers["content-type"].startswith("application/json")


def test_assets_path_returns_404_for_missing_file(
    client_with_dist: tuple[TestClient, Path],
) -> None:
    """Missing files under /assets/* must 404 via StaticFiles, NOT fall
    through to index.html — hashed bundle requests should fail loudly."""
    client, _dist = client_with_dist
    r = client.get("/assets/nope.js")
    assert r.status_code == 404


def test_static_mount_skipped_when_index_html_missing(
    settings: Settings, tmp_path: Path
) -> None:
    """A partial build (dist exists + assets/ exists but no index.html) must
    skip the mount rather than 500 on every request."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    # No index.html written.
    app = create_app(dist_dir=dist)
    with TestClient(app) as c:
        app.state.settings = settings
        r = c.get("/")
        assert r.status_code == 404


def test_static_mount_skipped_when_assets_dir_missing(
    settings: Settings, tmp_path: Path
) -> None:
    """A partial build (dist + index.html but no assets/) must skip rather
    than crash at mount time inside StaticFiles."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    # No assets/ dir.
    app = create_app(dist_dir=dist)
    with TestClient(app) as c:
        app.state.settings = settings
        r = c.get("/")
        assert r.status_code == 404
