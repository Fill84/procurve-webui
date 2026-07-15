"""Tests for /api/v1/backups/*.

Strategy:
  * Swap `download_config` / `upload_config` in the backups router module with
    async fakes so we never touch a real switch.
  * Override `get_transport` with a sentinel object.
  * Override `get_backup_store` with a fresh filesystem store under `tmp_path`.

No test in this file ever exercises the live switch.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.backups as backups_module
from app.backup_store import BackupStore
from app.deps import get_backup_store, get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.backup import ConfigBackup


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.0.2.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    monkeypatch.setenv("READ_ONLY", "true")
    monkeypatch.setenv("BACKUPS_DIR", str(tmp_path / "backups"))
    return Settings()


@pytest.fixture
def store(tmp_path: Path) -> BackupStore:
    return BackupStore(root=tmp_path / "store")


@pytest.fixture
def app(settings: Settings, store: BackupStore) -> FastAPI:
    a = create_app()
    a.state.settings = settings
    a.state.backup_store = store
    return a


@pytest.fixture
def client(app: FastAPI, store: BackupStore) -> Iterator[TestClient]:
    with TestClient(app) as c:
        # Re-bind settings + store after lifespan ran.
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        try:
            yield c
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backup(payload: bytes) -> ConfigBackup:
    return ConfigBackup.from_bytes(payload)


def _install_download(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> ConfigBackup:
    fake = _backup(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(backups_module, "download_config", fake_download)
    return fake


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_backups_empty(client: TestClient) -> None:
    r = client.get("/api/v1/backups")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_list_backups_returns_stored_entries_newest_first(
    client: TestClient, store: BackupStore
) -> None:
    first = store.save(_backup(b"first\n"), trigger="manual")
    second = store.save(_backup(b"second\n"), trigger="pre-write")
    r = client.get("/api/v1/backups")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [b["filename"] for b in body] == [second.filename, first.filename]
    assert body[0]["trigger"] == "pre-write"
    assert body[1]["trigger"] == "manual"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_backup_calls_download_and_saves(
    client: TestClient, store: BackupStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install_download(monkeypatch, b"running-config\n")
    r = client.post("/api/v1/backups", json={"trigger": "manual"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sha256"] == fake.sha256
    assert body["size"] == fake.size
    assert body["trigger"] == "manual"
    # Persisted on disk.
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].filename == body["filename"]
    assert (store.root / body["filename"]).read_bytes() == b"running-config\n"


def test_create_backup_defaults_trigger_to_manual(
    client: TestClient, store: BackupStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download(monkeypatch, b"x\n")
    r = client.post("/api/v1/backups")
    assert r.status_code == 201, r.text
    assert r.json()["trigger"] == "manual"


def test_create_backup_rejects_bogus_trigger(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download(monkeypatch, b"x\n")
    r = client.post("/api/v1/backups", json={"trigger": "bogus"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


def test_download_backup_returns_bytes(
    client: TestClient, store: BackupStore
) -> None:
    meta = store.save(_backup(b"binary-data\n"), trigger="manual")
    r = client.get(f"/api/v1/backups/{meta.filename}/download")
    assert r.status_code == 200, r.text
    assert r.content == b"binary-data\n"
    assert r.headers["content-type"] == "application/octet-stream"
    assert meta.filename in r.headers["content-disposition"]


def test_download_missing_returns_404(client: TestClient) -> None:
    r = client.get("/api/v1/backups/backup_00000000T000000Z.pcc/download")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_diff_backup_against_live(
    client: TestClient, store: BackupStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored = store.save(_backup(b"hostname old\n"), trigger="manual")
    _install_download(monkeypatch, b"hostname new\n")
    r = client.get(f"/api/v1/backups/{stored.filename}/diff")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    assert "-hostname old" in body
    assert "+hostname new" in body


def test_diff_missing_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download(monkeypatch, b"anything\n")
    r = client.get("/api/v1/backups/backup_00000000T000000Z.pcc/diff")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# restore (write-gated)
# ---------------------------------------------------------------------------


_CONFIRM_BODY = {"confirm_switch_host": "192.0.2.3"}  # equals settings.switch_host


def _install_prewrite_download(
    monkeypatch: pytest.MonkeyPatch, payload: bytes = b"live-config\n"
) -> ConfigBackup:
    """Patch the download used by write_with_autobackup's pre-write snapshot."""
    import app.write_safety as write_safety_module

    fake = _backup(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(write_safety_module, "download_config", fake_download)
    return fake


def test_restore_blocked_when_read_only_true(
    client: TestClient, store: BackupStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = store.save(_backup(b"cfg\n"), trigger="manual")
    called = False

    async def must_not_upload(
        transport: object, *, backup: ConfigBackup, **_: object
    ) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(backups_module, "upload_config", must_not_upload)
    r = client.post(f"/api/v1/backups/{meta.filename}/restore", json=_CONFIRM_BODY)
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "read_only"
    assert "READ_ONLY" in body["detail"]
    assert called is False


def test_restore_rejects_wrong_host_confirmation(
    app: FastAPI,
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    """Wrong/missing confirm_switch_host must 400 before any switch I/O."""
    settings.read_only = False
    app.state.settings = settings
    meta = store.save(_backup(b"cfg\n"), trigger="manual")
    called = False

    async def must_not_upload(transport: object, **_: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(backups_module, "upload_config", must_not_upload)
    r = client.post(
        f"/api/v1/backups/{meta.filename}/restore",
        json={"confirm_switch_host": "192.0.2.99"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "host_mismatch"
    assert called is False
    # And no pre-write backup was taken either.
    assert all(m.trigger != "pre-write" for m in store.list())


def test_restore_calls_upload_when_read_only_false(
    app: FastAPI,
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    # Flip the setting on the live app state — the router reads it from there.
    settings.read_only = False
    app.state.settings = settings

    meta = store.save(_backup(b"cfg\n"), trigger="manual")
    live = _install_prewrite_download(monkeypatch, b"live-config\n")
    uploaded: dict[str, ConfigBackup] = {}

    async def fake_upload(
        transport: object,
        *,
        backup: ConfigBackup,
        configname: str = "Config",
        reboot_after: bool = False,
        force: bool = False,
    ) -> None:
        uploaded["backup"] = backup

    monkeypatch.setattr(backups_module, "upload_config", fake_upload)
    r = client.post(f"/api/v1/backups/{meta.filename}/restore", json=_CONFIRM_BODY)
    assert r.status_code == 200, r.text
    assert uploaded["backup"].data == b"cfg\n"
    assert uploaded["backup"].sha256 == meta.sha256
    # A pre-restore snapshot of the LIVE config was saved before the upload
    # and surfaced in the response as the rollback point.
    body = r.json()
    pre = body["pre_restore_backup"]
    assert pre is not None
    saved = store.get_meta(pre)
    assert saved.trigger == "pre-write"
    assert saved.sha256 == live.sha256


def test_restore_missing_returns_404(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    settings.read_only = False
    app.state.settings = settings

    async def fake_upload(transport: object, **_: object) -> None:
        return None

    monkeypatch.setattr(backups_module, "upload_config", fake_upload)
    r = client.post(
        "/api/v1/backups/backup_00000000T000000Z.pcc/restore", json=_CONFIRM_BODY
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_backup(client: TestClient, store: BackupStore) -> None:
    meta = store.save(_backup(b"goodbye\n"), trigger="manual")
    assert (store.root / meta.filename).exists()
    r = client.delete(f"/api/v1/backups/{meta.filename}")
    assert r.status_code == 204, r.text
    assert not (store.root / meta.filename).exists()
    assert store.list() == []


def test_delete_missing_returns_404(client: TestClient) -> None:
    r = client.delete("/api/v1/backups/backup_00000000T000000Z.pcc")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# path-traversal safety
# ---------------------------------------------------------------------------


def test_download_rejects_path_traversal(client: TestClient) -> None:
    # URL-encoded path traversal must not escape the store. Regardless of how
    # the router resolves this, the response must not be 200 and must not
    # contain filesystem bytes from outside the store.
    r = client.get("/api/v1/backups/..%2F..%2Fetc%2Fpasswd/download")
    assert r.status_code in (400, 404, 422)


def test_delete_rejects_path_traversal(client: TestClient) -> None:
    r = client.delete("/api/v1/backups/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# live-sha
# ---------------------------------------------------------------------------


def test_live_sha_returns_current_sha(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install_download(monkeypatch, b"live running\n")
    r = client.get("/api/v1/backups/live-sha")
    assert r.status_code == 200, r.text
    assert r.json() == {"sha256": fake.sha256}


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_list_requires_auth(settings: Settings, store: BackupStore) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/backups")
        assert r.status_code == 401


def test_live_sha_requires_auth(settings: Settings, store: BackupStore) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/backups/live-sha")
        assert r.status_code == 401


def test_restore_requires_auth(settings: Settings, store: BackupStore) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.post("/api/v1/backups/backup_00000000T000000Z.pcc/restore")
        assert r.status_code == 401
