"""Tests for /api/v1/configuration/* (Task 3.5).

Sub-task 3.5a covers system info + IP config. This file will grow across
3.5b (ports), 3.5c (device features), 3.5d (QoS), 3.5e (support) in the
same shape.

Strategy
--------
* Patch the procurve_client operation functions on the configuration
  router module with async fakes. No test invokes the live switch.
* For writes, patch ``download_config`` on ``app.write_safety`` so the
  autobackup step doesn't reach the switch either.
* Override ``get_transport`` with a sentinel object and ``get_backup_store``
  with a fresh store rooted at ``tmp_path``.

Safety invariants verified here
-------------------------------
* ``PUT /configuration/ip`` is lockout-risky and requires
  ``confirm_switch_host`` matching ``settings.switch_host``.
* ``PUT /configuration/system`` and ``PUT /configuration/gateway`` do NOT
  require host confirmation (documented decision — see the router
  docstring and the Task 3.5a report).
* All three writes go through ``write_with_autobackup`` (pre-write backup
  appears on disk before the op runs).
"""
from __future__ import annotations

from collections.abc import Iterator
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.configuration as configuration_module
from app import write_safety
from app.backup_store import BackupStore
from app.deps import get_backup_store, get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.backup import ConfigBackup
from procurve_client.models.network import (
    ConfigWriteAck,
    IpConfigPage,
    IpMode,
    SystemInfoPage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
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
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
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
# Mock installers
# ---------------------------------------------------------------------------


def _install_download_config(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    fake = ConfigBackup.from_bytes(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(write_safety, "download_config", fake_download)


def _must_not_download(monkeypatch: pytest.MonkeyPatch) -> None:
    async def blow_up(transport: object) -> ConfigBackup:
        raise AssertionError("download_config should not run")

    monkeypatch.setattr(write_safety, "download_config", blow_up)


# ---------------------------------------------------------------------------
# System info (read)
# ---------------------------------------------------------------------------


def test_system_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> SystemInfoPage:
        return SystemInfoPage(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="HP2810_01",
            location="rack-3",
            contact="netops@example.com",
        )

    monkeypatch.setattr(configuration_module, "get_system_page", fake_get)
    r = client.get("/api/v1/configuration/system")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "HP2810_01"
    assert body["location"] == "rack-3"
    assert body["contact"] == "netops@example.com"
    assert body["mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_system_read_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/configuration/system")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# System info (write — no host confirmation)
# ---------------------------------------------------------------------------


_SYSTEM_BODY = {
    "request": {
        "name": "HP2810_01",
        "location": "rack-3",
        "contact": "netops@example.com",
    }
}


def test_system_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_system_info", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/configuration/system", json=_SYSTEM_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "read_only"
    assert called is False


def test_system_write_does_not_require_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Body WITHOUT ``confirm_switch_host`` should be accepted — system
    name / location / contact are not lockout-risky."""
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_system_info", fake_set)
    r = client.put("/api/v1/configuration/system", json=_SYSTEM_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_system_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append("set_system_info")
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_system_info", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/configuration/system", json=_SYSTEM_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_system_info"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_system_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True, raw_body="OK~")

    monkeypatch.setattr(configuration_module, "set_system_info", fake_set)
    r = client.put("/api/v1/configuration/system", json=_SYSTEM_BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["raw_body"] == "OK~"
    req = seen["request"]
    assert req.name == "HP2810_01"  # type: ignore[attr-defined]
    assert req.location == "rack-3"  # type: ignore[attr-defined]
    assert req.contact == "netops@example.com"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# IP config (read)
# ---------------------------------------------------------------------------


def test_ip_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> IpConfigPage:
        return IpConfigPage(
            vlan_id=1,
            mode=IpMode.MANUAL,
            ip_address=IPv4Address("192.168.178.3"),
            subnet_mask="255.255.255.0",
            gateway=IPv4Address("192.168.178.1"),
        )

    monkeypatch.setattr(configuration_module, "get_ip_page", fake_get)
    r = client.get("/api/v1/configuration/ip")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vlan_id"] == 1
    assert body["mode"] == int(IpMode.MANUAL)
    assert body["ip_address"] == "192.168.178.3"
    assert body["subnet_mask"] == "255.255.255.0"
    assert body["gateway"] == "192.168.178.1"


def test_ip_read_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/configuration/ip")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# IP config (write — lockout-risky: host confirm + autobackup)
# ---------------------------------------------------------------------------


_IP_BODY = {
    "request": {
        "gateway": "192.168.178.1",
        "vlan_id": 1,
        "mode": int(IpMode.MANUAL),
    },
    "confirm_switch_host": "192.168.178.3",
}


def test_ip_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_ip_config", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/configuration/ip", json=_IP_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_ip_write_requires_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def must_not_run(transport: object, **kw: object) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_ip_config", must_not_run)
    _must_not_download(monkeypatch)

    bad = {**_IP_BODY, "confirm_switch_host": "10.0.0.1"}
    r = client.put("/api/v1/configuration/ip", json=bad)
    assert r.status_code == 400
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "host_mismatch"
    assert called is False


def test_ip_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append("set_ip_config")
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_ip_config", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/configuration/ip", json=_IP_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_ip_config"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_ip_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_ip_config", fake_set)
    r = client.put("/api/v1/configuration/ip", json=_IP_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    req = seen["request"]
    assert str(req.gateway) == "192.168.178.1"  # type: ignore[attr-defined]
    assert req.vlan_id == 1  # type: ignore[attr-defined]
    assert int(req.mode) == int(IpMode.MANUAL)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Default gateway (write — no host confirmation)
# ---------------------------------------------------------------------------


_GATEWAY_BODY = {"request": {"gateway": "192.168.178.254"}}


def test_gateway_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(
        configuration_module, "set_default_gateway", must_not_run
    )
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/configuration/gateway", json=_GATEWAY_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_gateway_write_does_not_require_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Body WITHOUT ``confirm_switch_host`` is accepted — gateway changes
    are not considered lockout-risky (LAN session survives)."""
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_default_gateway", fake_set)
    r = client.put("/api/v1/configuration/gateway", json=_GATEWAY_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_gateway_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append("set_default_gateway")
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_default_gateway", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/configuration/gateway", json=_GATEWAY_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_default_gateway"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_gateway_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_default_gateway", fake_set)
    r = client.put("/api/v1/configuration/gateway", json=_GATEWAY_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    req = seen["request"]
    assert str(req.gateway) == "192.168.178.254"  # type: ignore[attr-defined]
