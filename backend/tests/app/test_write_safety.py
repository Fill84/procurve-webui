"""Tests for ``app.write_safety`` — the universal write-path guard.

No test in this module ever calls the live switch: ``download_config`` is
monkey-patched at the ``app.write_safety`` module level, and the "transport"
argument is a plain sentinel object since the real HTTP client is never
touched.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app import write_safety
from app.backup_store import BackupStore
from app.settings import Settings
from procurve_client.models.backup import ConfigBackup

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    read_only: bool,
    switch_host: str = "192.0.2.3",
) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", switch_host)
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    monkeypatch.setenv("READ_ONLY", "true" if read_only else "false")
    monkeypatch.setenv("BACKUPS_DIR", str(tmp_path / "backups"))
    return Settings()


@pytest.fixture
def store(tmp_path: Path) -> BackupStore:
    return BackupStore(root=tmp_path / "store")


@pytest.fixture
def transport() -> object:
    # Plain sentinel — write_with_autobackup forwards this to download_config,
    # which is mocked in every test, so a real ProcurveTransport isn't needed.
    return object()


def _fake_backup(payload: bytes = b"running-config\n") -> ConfigBackup:
    return ConfigBackup.from_bytes(payload)


# ---------------------------------------------------------------------------
# require_writable
# ---------------------------------------------------------------------------


def test_require_writable_raises_when_read_only_true(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=True)
    with pytest.raises(HTTPException) as exc_info:
        write_safety.require_writable(settings)
    assert exc_info.value.status_code == 403
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["error"] == "read_only"


def test_require_writable_passes_when_read_only_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=False)
    # No exception expected.
    write_safety.require_writable(settings)


# ---------------------------------------------------------------------------
# require_host_confirmation
# ---------------------------------------------------------------------------


def test_require_host_confirmation_mismatch_raises_400(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _make_settings(
        monkeypatch, tmp_path, read_only=False, switch_host="192.0.2.3"
    )
    with pytest.raises(HTTPException) as exc_info:
        write_safety.require_host_confirmation("10.0.0.1", settings)
    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["error"] == "host_mismatch"


def test_require_host_confirmation_matches_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _make_settings(
        monkeypatch, tmp_path, read_only=False, switch_host="192.0.2.3"
    )
    # Exact match — no exception.
    write_safety.require_host_confirmation("192.0.2.3", settings)
    # Leading/trailing whitespace is tolerated via .strip().
    write_safety.require_host_confirmation("  192.0.2.3  ", settings)


def test_require_host_confirmation_rejects_none_and_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=False)
    for bad in (None, "", "   "):
        with pytest.raises(HTTPException) as exc_info:
            write_safety.require_host_confirmation(bad, settings)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# write_with_autobackup
# ---------------------------------------------------------------------------


async def test_write_blocked_when_read_only_true(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: BackupStore,
    transport: object,
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=True)

    called: list[str] = []

    async def fake_download(_transport: object) -> ConfigBackup:
        called.append("download")
        return _fake_backup()

    async def write() -> str:
        called.append("write")
        return "ok"

    monkeypatch.setattr(write_safety, "download_config", fake_download)

    with pytest.raises(HTTPException) as exc_info:
        await write_safety.write_with_autobackup(
            settings=settings,
            store=store,
            transport=transport,  # type: ignore[arg-type]
            write=write,
        )
    assert exc_info.value.status_code == 403
    # Neither download nor write fired: the gate short-circuits first.
    assert called == []
    assert store.list() == []


async def test_write_proceeds_when_read_only_false_and_backup_saved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: BackupStore,
    transport: object,
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=False)
    fake = _fake_backup(b"config-v1\n")

    async def fake_download(_transport: object) -> ConfigBackup:
        return fake

    async def write() -> str:
        return "write-ran"

    monkeypatch.setattr(write_safety, "download_config", fake_download)

    result = await write_safety.write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,  # type: ignore[arg-type]
        write=write,
    )
    assert result == "write-ran"

    # Exactly one pre-write backup landed on disk.
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"
    assert listed[0].sha256 == fake.sha256


async def test_backup_stored_before_write_function_called(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: BackupStore,
    transport: object,
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=False)
    order: list[str] = []

    async def fake_download(_transport: object) -> ConfigBackup:
        order.append("download")
        return _fake_backup()

    original_save = store.save

    def save_spy(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(write_safety, "download_config", fake_download)
    monkeypatch.setattr(store, "save", save_spy)

    async def write() -> None:
        order.append("write")

    await write_safety.write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,  # type: ignore[arg-type]
        write=write,
    )
    # Strict ordering: the pre-write backup is persisted *before* the write
    # callable is ever invoked. This is the core invariant the helper
    # exists to enforce.
    assert order == ["download", "save", "write"]


async def test_write_aborted_when_backup_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: BackupStore,
    transport: object,
) -> None:
    settings = _make_settings(monkeypatch, tmp_path, read_only=False)

    class BackupDownloadError(RuntimeError):
        pass

    async def fake_download(_transport: object) -> ConfigBackup:
        raise BackupDownloadError("switch unreachable")

    write_called = False

    async def write() -> None:
        nonlocal write_called
        write_called = True

    monkeypatch.setattr(write_safety, "download_config", fake_download)

    with pytest.raises(BackupDownloadError):
        await write_safety.write_with_autobackup(
            settings=settings,
            store=store,
            transport=transport,  # type: ignore[arg-type]
            write=write,
        )
    # The write coroutine must never have run, and no backup is persisted.
    assert write_called is False
    assert store.list() == []
