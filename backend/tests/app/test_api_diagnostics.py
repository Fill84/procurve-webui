"""Tests for /api/v1/diagnostics/* (Task 3.3).

Strategy:
  * Swap the procurve_client operation functions (``ping``, ``link_test``,
    ``get_configuration_report``, ``device_reset``) on the diagnostics router
    module with async fakes. No test invokes the live switch.
  * For ``device-reset`` we also mock ``download_config`` on the
    ``write_safety`` module so the autobackup step doesn't attempt switch I/O.
  * Override ``get_transport`` with a sentinel object.
  * For the reset test we override ``get_backup_store`` with a fresh store
    rooted at ``tmp_path`` so we can assert the pre-write backup landed.

Automated tooling never invokes ``device_reset`` against a real switch —
only the operator runs it manually, with a verified backup in hand.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.diagnostics as diagnostics_module
from app import write_safety
from app.backup_store import BackupStore
from app.deps import get_backup_store, get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.backup import ConfigBackup
from procurve_client.models.diagnostics import (
    ConfigurationReport,
    DeviceResetResponse,
    PingResult,
)
from procurve_client.parsing import parse_running_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.0.2.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    monkeypatch.setenv("READ_ONLY", "false")
    monkeypatch.setenv("BACKUPS_DIR", str(tmp_path / "backups"))
    return Settings()


@pytest.fixture
def read_only_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Settings:
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
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        try:
            yield c
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _install_ping(
    monkeypatch: pytest.MonkeyPatch, result: PingResult
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def fake_ping(transport: object, **kwargs: object) -> PingResult:
        calls.append(kwargs)
        return result

    monkeypatch.setattr(diagnostics_module, "ping", fake_ping)
    return calls


def _install_link_test(
    monkeypatch: pytest.MonkeyPatch, result: PingResult
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    async def fake_link(transport: object, **kwargs: object) -> PingResult:
        calls.append(kwargs)
        return result

    monkeypatch.setattr(diagnostics_module, "link_test", fake_link)
    return calls


def _install_config_report(
    monkeypatch: pytest.MonkeyPatch, report: ConfigurationReport
) -> None:
    async def fake_report(transport: object) -> ConfigurationReport:
        return report

    monkeypatch.setattr(diagnostics_module, "get_configuration_report", fake_report)


def _install_device_reset(
    monkeypatch: pytest.MonkeyPatch, response: DeviceResetResponse
) -> list[int]:
    calls: list[int] = []

    async def fake_reset(transport: object) -> DeviceResetResponse:
        calls.append(1)
        return response

    monkeypatch.setattr(diagnostics_module, "device_reset", fake_reset)
    return calls


def _install_download_config(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    fake = ConfigBackup.from_bytes(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(write_safety, "download_config", fake_download)


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------


def test_ping_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_ping(
        monkeypatch,
        PingResult(successes=10, failures=0, raw_html="<html>ok</html>"),
    )
    r = client.post(
        "/api/v1/diagnostics/ping",
        json={"destination": "8.8.8.8", "packet_count": 10, "timeout_s": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["successes"] == 10
    assert body["failures"] == 0
    assert body["raw_html"] == "<html>ok</html>"
    # The route forwarded the right kwargs to the client.
    assert len(calls) == 1
    assert calls[0]["destination"] == "8.8.8.8"
    assert calls[0]["packet_count"] == 10
    assert calls[0]["timeout_s"] == 5


def test_ping_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kwargs: object) -> PingResult:
        nonlocal called
        called = True
        return PingResult(successes=0, failures=0, raw_html="")

    monkeypatch.setattr(diagnostics_module, "ping", must_not_run)
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.post(
            "/api/v1/diagnostics/ping",
            json={"destination": "8.8.8.8"},
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    body = r.json()
    detail = body  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


def test_ping_requires_auth(settings: Settings, store: BackupStore) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.post(
            "/api/v1/diagnostics/ping", json={"destination": "8.8.8.8"}
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Link test
# ---------------------------------------------------------------------------


def test_link_test_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_link_test(
        monkeypatch,
        PingResult(successes=5, failures=1, raw_html="<html>link</html>"),
    )
    r = client.post(
        "/api/v1/diagnostics/link-test",
        json={
            "destination": "00-1D-B3-B7-0E-00",
            "packet_count": 6,
            "timeout_s": 2,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["successes"] == 5
    assert body["failures"] == 1
    assert len(calls) == 1
    assert calls[0]["destination"] == "00-1D-B3-B7-0E-00"
    assert calls[0]["packet_count"] == 6
    assert calls[0]["timeout_s"] == 2


def test_link_test_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kwargs: object) -> PingResult:
        nonlocal called
        called = True
        return PingResult(successes=0, failures=0, raw_html="")

    monkeypatch.setattr(diagnostics_module, "link_test", must_not_run)
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.post(
            "/api/v1/diagnostics/link-test",
            json={"destination": "00-1D-B3-B7-0E-00"},
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


# ---------------------------------------------------------------------------
# Configuration report
# ---------------------------------------------------------------------------


def test_config_report_returns_text(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_text = "hostname HP2810_01\n; firmware N.11.78\n"
    report = ConfigurationReport(
        raw_html=f"<html><pre>{config_text}</pre></html>",
        config_text=config_text,
        running_config=parse_running_config(config_text),
    )
    _install_config_report(monkeypatch, report)
    r = client.get("/api/v1/diagnostics/configuration-report")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["config_text"] == config_text
    assert "<pre>" in body["raw_html"]


def test_config_report_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/diagnostics/configuration-report")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Device reset (FULL safety pattern)
# ---------------------------------------------------------------------------


def test_device_reset_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_reset(transport: object) -> DeviceResetResponse:
        nonlocal called
        called = True
        return DeviceResetResponse(initiated=True)

    # Even if the gate leaked, the op itself mustn't be reached.
    monkeypatch.setattr(diagnostics_module, "device_reset", must_not_reset)
    # Autobackup download also mustn't fire (require_writable should block first).
    async def must_not_download(transport: object) -> ConfigBackup:
        raise AssertionError("download_config should not run in read-only mode")

    monkeypatch.setattr(write_safety, "download_config", must_not_download)
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.post(
            "/api/v1/diagnostics/device-reset",
            json={"confirm_switch_host": "192.0.2.3"},
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    body = r.json()
    detail = body  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


def test_device_reset_requires_host_confirmation_match(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def must_not_reset(transport: object) -> DeviceResetResponse:
        nonlocal called
        called = True
        return DeviceResetResponse(initiated=True)

    monkeypatch.setattr(diagnostics_module, "device_reset", must_not_reset)

    async def must_not_download(transport: object) -> ConfigBackup:
        raise AssertionError(
            "download_config must not run when host confirmation fails"
        )

    monkeypatch.setattr(write_safety, "download_config", must_not_download)
    r = client.post(
        "/api/v1/diagnostics/device-reset",
        json={"confirm_switch_host": "10.0.0.1"},
    )
    assert r.status_code == 400
    body = r.json()
    detail = body  # flat {error, detail} envelope
    assert detail.get("error") == "host_mismatch"
    assert called is False


def test_device_reset_creates_pre_write_backup_before_call(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_reset(transport: object) -> DeviceResetResponse:
        order.append("reset")
        return DeviceResetResponse(initiated=True)

    monkeypatch.setattr(diagnostics_module, "device_reset", fake_reset)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.post(
        "/api/v1/diagnostics/device-reset",
        json={"confirm_switch_host": "192.0.2.3"},
    )
    assert r.status_code == 200, r.text
    # Backup saved before reset was dispatched.
    assert order == ["save", "reset"]
    # And a pre-write backup now exists on disk.
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_device_reset_happy_path(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"running-config\n")
    calls = _install_device_reset(
        monkeypatch,
        DeviceResetResponse(initiated=True, message="rebooting"),
    )
    r = client.post(
        "/api/v1/diagnostics/device-reset",
        json={"confirm_switch_host": "192.0.2.3"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["initiated"] is True
    assert body["message"] == "rebooting"
    assert len(calls) == 1
