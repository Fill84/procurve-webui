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
    DeviceFeaturesPage,
    FaultDetectionPage,
    FaultSensitivity,
    IpConfigPage,
    IpMode,
    MonitorPage,
    SupportPage,
    SystemInfoPage,
)
from procurve_client.models.port import (
    BobDevice,
    BobPort,
    BobPortsResponse,
    PortConfig,
    PortConfigList,
    PortForm,
    PortMode,
)
from procurve_client.models.qos import (
    ApplyPolicy,
    CosAppEntry,
    CosAppList,
    CosTosMode,
    CosUserEntry,
    CosUserList,
    CosVlanEntry,
    CosVlanList,
    DiffservEntry,
    DiffservTable,
    DscpPolicy,
    DscpTable,
    QosWriteAck,
)

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
    detail = r.json()  # flat {error, detail} envelope
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
            ip_address=IPv4Address("192.0.2.3"),
            subnet_mask="255.255.255.0",
            gateway=IPv4Address("192.168.178.1"),
        )

    monkeypatch.setattr(configuration_module, "get_ip_page", fake_get)
    r = client.get("/api/v1/configuration/ip")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vlan_id"] == 1
    assert body["mode"] == int(IpMode.MANUAL)
    assert body["ip_address"] == "192.0.2.3"
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
    "confirm_switch_host": "192.0.2.3",
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
    detail = r.json()  # flat {error, detail} envelope
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


# ---------------------------------------------------------------------------
# Ports — list (read)
# ---------------------------------------------------------------------------


def _sample_port_row(port: int, name: str = "") -> PortConfig:
    return PortConfig(
        port=port,
        port_name=name,
        port_type_label="",
        port_type="10/100/1000TX",
        enabled=True,
        config_status=".",
        config_mode="Auto",
        trunk="",
        flow_control=False,
        extra=0,
    )


def test_ports_list_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> PortConfigList:
        return PortConfigList(
            ports=[
                _sample_port_row(1, "uplink"),
                _sample_port_row(2),
                _sample_port_row(3, "server-a"),
            ]
        )

    monkeypatch.setattr(configuration_module, "get_portscfg", fake_get)
    r = client.get("/api/v1/configuration/ports")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ports"]) == 3
    assert body["ports"][0]["port"] == 1
    assert body["ports"][0]["port_name"] == "uplink"
    assert body["ports"][2]["port_name"] == "server-a"


def test_ports_list_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/configuration/ports")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Ports — per-port form (read)
# ---------------------------------------------------------------------------


def test_port_form_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    async def fake_get(transport: object, **kw: object) -> PortForm:
        seen.update(kw)
        return PortForm(
            ports=[5],
            port_name="server-a",
            admin_enabled=True,
            mode=PortMode.AUTO,
            flow_control_enabled=False,
        )

    monkeypatch.setattr(configuration_module, "get_port_form", fake_get)
    r = client.get("/api/v1/configuration/ports/5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ports"] == [5]
    assert body["port_name"] == "server-a"
    assert body["admin_enabled"] is True
    assert body["mode"] == int(PortMode.AUTO)
    assert body["flow_control_enabled"] is False
    # The router must pass the path param as a single-element list.
    assert seen["ports"] == [5]


def test_port_form_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/configuration/ports/5")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Ports — write (per-port)
# ---------------------------------------------------------------------------


_PORT_BODY = {
    "request": {
        "ports": [5],
        "name": "server-a",
        "admin_enabled": True,
        "mode": int(PortMode.AUTO),
        "flow_control_enabled": False,
    }
}


def test_port_config_write_blocked_when_read_only(
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

    monkeypatch.setattr(configuration_module, "set_port_config", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/configuration/ports/5", json=_PORT_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_port_config_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append("set_port_config")
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_port_config", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/configuration/ports/5", json=_PORT_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_port_config"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_port_config_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True, raw_body="OK~")

    monkeypatch.setattr(configuration_module, "set_port_config", fake_set)
    r = client.put("/api/v1/configuration/ports/5", json=_PORT_BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["raw_body"] == "OK~"
    req = seen["request"]
    assert req.ports == [5]  # type: ignore[attr-defined]
    assert req.name == "server-a"  # type: ignore[attr-defined]
    assert req.admin_enabled is True  # type: ignore[attr-defined]
    assert int(req.mode) == int(PortMode.AUTO)  # type: ignore[attr-defined]
    assert req.flow_control_enabled is False  # type: ignore[attr-defined]


def test_port_config_write_path_overrides_body_ports(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The URL path is authoritative — a stale ``request.ports`` in the body
    must be replaced with the path's port before the op runs."""
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_port_config", fake_set)

    # Body says ports=[9]; URL says /ports/5 → op must see [5].
    body = {
        "request": {
            "ports": [9],
            "name": "mismatch",
            "admin_enabled": True,
            "mode": int(PortMode.AUTO),
            "flow_control_enabled": False,
        }
    }
    r = client.put("/api/v1/configuration/ports/5", json=body)
    assert r.status_code == 200, r.text
    req = seen["request"]
    assert req.ports == [5]  # type: ignore[attr-defined]
    assert req.name == "mismatch"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Device features / fault detection / monitor / bob-ports — reads
# ---------------------------------------------------------------------------


def test_device_features_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> DeviceFeaturesPage:
        return DeviceFeaturesPage(
            vlan_count=1, crip_stat="0", igmp=True, spanning_tree=False
        )

    monkeypatch.setattr(configuration_module, "get_devfeatures_page", fake_get)
    r = client.get("/api/v1/configuration/device-features")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vlan_count"] == 1
    assert body["igmp"] is True
    assert body["spanning_tree"] is False


def test_fault_detection_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> FaultDetectionPage:
        return FaultDetectionPage(sensitivity=FaultSensitivity.MEDIUM, dps=12)

    monkeypatch.setattr(
        configuration_module, "get_faultdetect_page", fake_get
    )
    r = client.get("/api/v1/configuration/fault-detection")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sensitivity"] == int(FaultSensitivity.MEDIUM)
    assert body["dps"] == 12


def test_monitor_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> MonitorPage:
        return MonitorPage(
            enabled=True,
            candidate_dest_ports=[1, 2, 3],
            selected_dest_port=2,
        )

    monkeypatch.setattr(configuration_module, "get_monitor_page", fake_get)
    r = client.get("/api/v1/configuration/monitor")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["candidate_dest_ports"] == [1, 2, 3]
    assert body["selected_dest_port"] == 2


def test_bob_ports_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> BobPortsResponse:
        return BobPortsResponse(
            device=BobDevice(codename="J9021A", port_count=24),
            ports=[
                BobPort(
                    port=1, kind="copper", label="1", link=True, enabled=True
                ),
                BobPort(
                    port=2,
                    kind="copper",
                    label="2",
                    link=False,
                    enabled=False,
                ),
            ],
        )

    monkeypatch.setattr(configuration_module, "get_bobports", fake_get)
    r = client.get("/api/v1/configuration/bob-ports")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["device"]["codename"] == "J9021A"
    assert body["device"]["port_count"] == 24
    assert len(body["ports"]) == 2
    assert body["ports"][0]["enabled"] is True
    assert body["ports"][1]["enabled"] is False


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/configuration/device-features",
        "/api/v1/configuration/fault-detection",
        "/api/v1/configuration/monitor",
        "/api/v1/configuration/bob-ports",
        "/api/v1/configuration/support-page",
    ],
)
def test_read_requires_auth(
    settings: Settings, store: BackupStore, path: str
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get(path)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Device features / fault detection / monitor / bob-ports — writes
# ---------------------------------------------------------------------------

_DEV_FEATURES_BODY = {
    "request": {
        "endpoint": "/cgi/feature_set",
        "vlan_id": 1,
        "igmp": True,
        "spanning_tree": False,
    }
}

_FAULT_DETECTION_BODY = {
    "request": {"sensitivity": int(FaultSensitivity.MEDIUM)}
}

_MONITOR_BODY = {
    "request": {"enabled": True, "dest_port": 2, "source_ports": [1, 3]},
}

_BOB_PORTS_BODY = {"request": {"enable": True, "ports": [1, 2, 3]}}


# The 4 write endpoints share the same gate pattern. Parametrize the
# READ_ONLY test over all of them.

_WRITE_CASES = [
    (
        "/api/v1/configuration/device-features",
        "set_device_features",
        _DEV_FEATURES_BODY,
    ),
    (
        "/api/v1/configuration/fault-detection",
        "set_fault_detection",
        _FAULT_DETECTION_BODY,
    ),
    ("/api/v1/configuration/monitor", "set_monitor", _MONITOR_BODY),
    ("/api/v1/configuration/bob-ports", "set_bobports", _BOB_PORTS_BODY),
]


@pytest.mark.parametrize("path,op_name,body", _WRITE_CASES)
def test_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    op_name: str,
    body: dict[str, object],
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, op_name, must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put(path, json=body)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json()  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


@pytest.mark.parametrize("path,op_name,body", _WRITE_CASES)
def test_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    op_name: str,
    body: dict[str, object],
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append(op_name)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, op_name, fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put(path, json=body)
    assert r.status_code == 200, r.text
    assert order == ["save", op_name]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_device_features_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True, raw_body="OK~")

    monkeypatch.setattr(configuration_module, "set_device_features", fake_set)
    r = client.put(
        "/api/v1/configuration/device-features", json=_DEV_FEATURES_BODY
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["raw_body"] == "OK~"
    req = seen["request"]
    assert req.endpoint == "/cgi/feature_set"  # type: ignore[attr-defined]
    assert req.vlan_id == 1  # type: ignore[attr-defined]
    assert req.igmp is True  # type: ignore[attr-defined]
    assert req.spanning_tree is False  # type: ignore[attr-defined]


def test_fault_detection_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_fault_detection", fake_set)
    r = client.put(
        "/api/v1/configuration/fault-detection", json=_FAULT_DETECTION_BODY
    )
    assert r.status_code == 200, r.text
    req = seen["request"]
    assert int(req.sensitivity) == int(FaultSensitivity.MEDIUM)  # type: ignore[attr-defined]


def test_monitor_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_monitor", fake_set)
    r = client.put("/api/v1/configuration/monitor", json=_MONITOR_BODY)
    assert r.status_code == 200, r.text
    req = seen["request"]
    assert req.enabled is True  # type: ignore[attr-defined]
    assert req.dest_port == 2  # type: ignore[attr-defined]
    assert req.source_ports == [1, 3]  # type: ignore[attr-defined]


def test_bob_ports_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_bobports", fake_set)
    r = client.put("/api/v1/configuration/bob-ports", json=_BOB_PORTS_BODY)
    assert r.status_code == 200, r.text
    req = seen["request"]
    assert req.enable is True  # type: ignore[attr-defined]
    assert req.ports == [1, 2, 3]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# QoS — reads
# ---------------------------------------------------------------------------


def test_qos_cos_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> CosAppList:
        return CosAppList(
            entries=[
                CosAppEntry(
                    application_name="http (80)",
                    port_number=80,
                    type="TCP",
                    dscp="No Override",
                    priority="No Override",
                )
            ]
        )

    monkeypatch.setattr(configuration_module, "get_cos_appt", fake_get)
    r = client.get("/api/v1/configuration/qos/cos")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["application_name"] == "http (80)"
    assert body["entries"][0]["type"] == "TCP"


def test_qos_user_pri_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> CosUserList:
        return CosUserList(
            entries=[
                CosUserEntry(
                    ip_address="10.0.0.5",
                    dscp_policy="No Override",
                    priority="No Override",
                )
            ]
        )

    monkeypatch.setattr(configuration_module, "get_cos_userpri", fake_get)
    r = client.get("/api/v1/configuration/qos/user-pri")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entries"][0]["ip_address"] == "10.0.0.5"


def test_qos_vlan_pri_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> CosVlanList:
        return CosVlanList(
            entries=[
                CosVlanEntry(
                    vlan_id=1,
                    vlan_label="DEFAULT_VLAN",
                    dscp_policy="No Override",
                    priority="No Override",
                )
            ]
        )

    monkeypatch.setattr(configuration_module, "get_cos_vlanpri", fake_get)
    r = client.get("/api/v1/configuration/qos/vlan-pri")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entries"][0]["vlan_id"] == 1
    assert body["entries"][0]["vlan_label"] == "DEFAULT_VLAN"


def test_qos_dscp_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> DscpTable:
        return DscpTable(
            rows=[
                DscpPolicy(
                    row_index=1, codepoint="000000", priority_label="0"
                ),
                DscpPolicy(
                    row_index=2, codepoint="000001", priority_label="No Override"
                ),
            ]
        )

    monkeypatch.setattr(configuration_module, "get_dscptable", fake_get)
    r = client.get("/api/v1/configuration/qos/dscp")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 2
    assert body["rows"][0]["codepoint"] == "000000"
    assert body["rows"][1]["priority_label"] == "No Override"


def test_qos_diffserv_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> DiffservTable:
        return DiffservTable(
            rows=[
                DiffservEntry(
                    row_index=1,
                    inbound_codepoint="000000",
                    dscp_policy="No Override",
                    priority_label="0",
                )
            ]
        )

    monkeypatch.setattr(configuration_module, "get_diffserv", fake_get)
    r = client.get("/api/v1/configuration/qos/diffserv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"][0]["inbound_codepoint"] == "000000"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/configuration/qos/cos",
        "/api/v1/configuration/qos/user-pri",
        "/api/v1/configuration/qos/vlan-pri",
        "/api/v1/configuration/qos/dscp",
        "/api/v1/configuration/qos/diffserv",
    ],
)
def test_qos_read_requires_auth(
    settings: Settings, store: BackupStore, path: str
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get(path)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# QoS — writes
# ---------------------------------------------------------------------------

_QOS_COS_BODY = {
    "request": {
        "action": "Add",
        "app_id": 1,
        "protocol": "TCP",
        "policy_mode": int(ApplyPolicy.NO_OVERRIDE),
    }
}

_QOS_USER_PRI_BODY = {
    "request": {
        "action": "Add",
        "address": "10.0.0.5",
        "policy_mode": int(ApplyPolicy.DSCP),
        "dscp": 46,
    }
}

_QOS_VLAN_PRI_BODY = {
    "request": {
        "vlan_id": 1,
        "dscp": 46,
        "priority_8021p": 255,
    }
}

_QOS_MODE_BODY = {"request": {"mode": int(CosTosMode.DIFFSERV)}}

_QOS_DSCP_BODY = {"request": {"row_index": 47, "priority_8021p": 5}}

_QOS_DIFFSERV_BODY = {"request": {"row_index": 47, "dscp": 46}}

_QOS_COS_PROTO_BODY = {"request": {"apply": "Apply Changes"}}

_QOS_WRITE_CASES = [
    ("/api/v1/configuration/qos/cos", "set_cos_appt", _QOS_COS_BODY),
    (
        "/api/v1/configuration/qos/user-pri",
        "set_cos_userpri",
        _QOS_USER_PRI_BODY,
    ),
    (
        "/api/v1/configuration/qos/vlan-pri",
        "set_cos_vlanpri",
        _QOS_VLAN_PRI_BODY,
    ),
    ("/api/v1/configuration/qos/mode", "set_costos_mode", _QOS_MODE_BODY),
    ("/api/v1/configuration/qos/dscp", "set_dscptable", _QOS_DSCP_BODY),
    (
        "/api/v1/configuration/qos/diffserv",
        "set_diffserv",
        _QOS_DIFFSERV_BODY,
    ),
    (
        "/api/v1/configuration/qos/cos-proto",
        "set_cosproto",
        _QOS_COS_PROTO_BODY,
    ),
]


@pytest.mark.parametrize("path,op_name,body", _QOS_WRITE_CASES)
def test_qos_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    op_name: str,
    body: dict[str, object],
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> QosWriteAck:
        nonlocal called
        called = True
        return QosWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, op_name, must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put(path, json=body)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json()  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


@pytest.mark.parametrize("path,op_name,body", _QOS_WRITE_CASES)
def test_qos_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    op_name: str,
    body: dict[str, object],
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> QosWriteAck:
        order.append(op_name)
        return QosWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, op_name, fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put(path, json=body)
    assert r.status_code == 200, r.text
    assert order == ["save", op_name]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


@pytest.mark.parametrize("path,op_name,body", _QOS_WRITE_CASES)
def test_qos_write_happy_path(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    op_name: str,
    body: dict[str, object],
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> QosWriteAck:
        seen.update(kw)
        return QosWriteAck(ok=True, raw_body="OK~")

    monkeypatch.setattr(configuration_module, op_name, fake_set)
    r = client.put(path, json=body)
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp["ok"] is True
    assert resp["raw_body"] == "OK~"
    # Each op is called with a `request=` kwarg carrying a pydantic model.
    assert "request" in seen


# ---------------------------------------------------------------------------
# Support page form (Task 3.5e)
#
# The Configuration tab's editable Support-page form — two URL fields.
# Distinct from Phase 3.2's static /api/v1/support info view.
# ---------------------------------------------------------------------------


_SUPPORT_PAGE_BODY = {
    "request": {
        "support_url": "http://support.example.com",
        "mgmt_url": "http://mgmt.example.com",
    }
}


def test_configuration_support_page_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> SupportPage:
        return SupportPage(
            support_url="http://support.example.com",
            mgmt_url="http://mgmt.example.com",
        )

    monkeypatch.setattr(configuration_module, "get_support_page", fake_get)
    r = client.get("/api/v1/configuration/support-page")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["support_url"] == "http://support.example.com"
    assert body["mgmt_url"] == "http://mgmt.example.com"


def test_configuration_support_page_write_blocked_when_read_only(
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

    monkeypatch.setattr(configuration_module, "set_support", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put(
            "/api/v1/configuration/support-page", json=_SUPPORT_PAGE_BODY
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json()  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


def test_configuration_support_page_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        order.append("set_support")
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(configuration_module, "set_support", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put(
        "/api/v1/configuration/support-page", json=_SUPPORT_PAGE_BODY
    )
    assert r.status_code == 200, r.text
    assert order == ["save", "set_support"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_configuration_support_page_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> ConfigWriteAck:
        seen.update(kw)
        return ConfigWriteAck(ok=True, raw_body="OK~")

    monkeypatch.setattr(configuration_module, "set_support", fake_set)
    r = client.put(
        "/api/v1/configuration/support-page", json=_SUPPORT_PAGE_BODY
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["raw_body"] == "OK~"
    req = seen["request"]
    assert req.support_url == "http://support.example.com"  # type: ignore[attr-defined]
    assert req.mgmt_url == "http://mgmt.example.com"  # type: ignore[attr-defined]
