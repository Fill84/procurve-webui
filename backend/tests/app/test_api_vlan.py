"""Tests for /api/v1/vlans/* (Phase 4, F1).

Strategy mirrors test_api_security.py:
  * Patch the procurve_client VLAN operation functions on the vlan router
    module with async fakes — no live switch I/O.
  * For writes, patch ``download_config`` on ``write_safety`` so the
    autobackup step doesn't attempt switch I/O either.
  * Override ``get_transport`` / ``get_backup_store``.

SAFETY INVARIANTS VERIFIED HERE
-------------------------------
- EVERY VLAN write (create / delete / rename / ports) is lockout-risky:
  each requires ``confirm_switch_host`` to match ``settings.switch_host``
  and is blocked by READ_ONLY before any switch I/O.
- All writes go through ``write_with_autobackup`` (pre-write backup is
  persisted before the op runs).
- Route path ids are authoritative over body copies (rename / ports).
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.vlan as vlan_module
from app import write_safety
from app.backup_store import BackupStore
from app.deps import get_backup_store, get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.errors import OperationError
from procurve_client.models.backup import ConfigBackup
from procurve_client.models.vlan import (
    Vlan,
    VlanList,
    VlanMembership,
    VlanMembershipList,
    VlanPortMode,
    VlanSummary,
    VlanWriteAck,
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


def _install_download_config(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    fake = ConfigBackup.from_bytes(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(write_safety, "download_config", fake_download)


def _must_not_download(monkeypatch: pytest.MonkeyPatch) -> None:
    async def blow_up(transport: object) -> ConfigBackup:
        raise AssertionError("download_config should not run")

    monkeypatch.setattr(write_safety, "download_config", blow_up)


_DEFAULT_VLAN = Vlan(
    vlan_id=1,
    vlan_name="DEFAULT_VLAN",
    vlan_type="STATIC",
    tagged_ports="None",
    gvrp_ports="None",
    untagged_ports="1-24",
    forbid_ports="None",
    auto_ports="None",
)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_vlans_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> VlanList:
        return VlanList(vlans=[_DEFAULT_VLAN])

    monkeypatch.setattr(vlan_module, "get_vlans_all", fake_get)
    r = client.get("/api/v1/vlans")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vlans"][0]["vlan_id"] == 1
    assert body["vlans"][0]["vlan_name"] == "DEFAULT_VLAN"


def test_vlans_read_requires_auth(settings: Settings, store: BackupStore) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/vlans")
        assert r.status_code == 401


def test_vlan_ports_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(
        transport: object, *, vlan_id: int
    ) -> VlanMembershipList:
        assert vlan_id == 10
        return VlanMembershipList(
            vlan_id=10,
            gvrp_enable=False,
            ports=[
                VlanMembership(
                    port_name="1", port_id=1, mode=VlanPortMode.UNTAGGED
                )
            ],
        )

    monkeypatch.setattr(vlan_module, "get_vlan_ports", fake_get)
    r = client.get("/api/v1/vlans/10/ports")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vlan_id"] == 10
    assert body["ports"][0]["mode"] == VlanPortMode.UNTAGGED


# ---------------------------------------------------------------------------
# Writes — shared bodies
# ---------------------------------------------------------------------------


_ADD_BODY = {
    "request": {"vlan_id": 10, "vlan_name": "IoT"},
    "confirm_switch_host": "192.0.2.3",
}
_DEL_BODY = {
    "request": {"vlan_ids": [10, 20]},
    "confirm_switch_host": "192.0.2.3",
}
_REN_BODY = {"vlan_name": "Lab", "confirm_switch_host": "192.0.2.3"}
_PORTS_BODY = {
    "request": {
        "vlan_id": 10,
        "changes": [{"port_id": 3, "mode": 2}],
    },
    "confirm_switch_host": "192.0.2.3",
}

_WRITE_CALLS = [
    ("post", "/api/v1/vlans", _ADD_BODY, "add_vlan"),
    ("post", "/api/v1/vlans/delete", _DEL_BODY, "delete_vlans"),
    ("put", "/api/v1/vlans/10/name", _REN_BODY, "rename_vlan"),
    ("put", "/api/v1/vlans/10/ports", _PORTS_BODY, "set_vlan_ports"),
]


@pytest.mark.parametrize(("method", "path", "body", "op_name"), _WRITE_CALLS)
def test_every_vlan_write_requires_host_confirmation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, object],
    op_name: str,
) -> None:
    called = False

    async def must_not_run(transport: object, **kw: object) -> VlanWriteAck:
        nonlocal called
        called = True
        return VlanWriteAck(ok=True)

    monkeypatch.setattr(vlan_module, op_name, must_not_run)
    _must_not_download(monkeypatch)

    bad = {**body, "confirm_switch_host": "10.0.0.1"}
    r = getattr(client, method)(path, json=bad)
    assert r.status_code == 400
    assert r.json().get("error") == "host_mismatch"
    assert called is False


@pytest.mark.parametrize(("method", "path", "body", "op_name"), _WRITE_CALLS)
def test_every_vlan_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    body: dict[str, object],
    op_name: str,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> VlanWriteAck:
        nonlocal called
        called = True
        return VlanWriteAck(ok=True)

    monkeypatch.setattr(vlan_module, op_name, must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = getattr(c, method)(path, json=body)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert r.json().get("error") == "read_only"
    assert called is False


def test_add_vlan_creates_pre_write_backup_first(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_add(transport: object, **kw: object) -> VlanWriteAck:
        order.append("add_vlan")
        return VlanWriteAck(
            ok=True, vlans=[VlanSummary(vlan_id=10, vlan_name="IoT")]
        )

    monkeypatch.setattr(vlan_module, "add_vlan", fake_add)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.post("/api/v1/vlans", json=_ADD_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "add_vlan"]
    body = r.json()
    assert body["ok"] is True
    assert body["vlans"][0]["vlan_id"] == 10
    # Backup persisted with the pre-write trigger.
    metas = store.list()
    assert len(metas) == 1
    assert metas[0].trigger == "pre-write"


def test_add_vlan_rejects_invalid_name_before_switch_io(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Model validation (no '~', no spaces, ≤12 chars) happens at the API
    boundary — a bad name never reaches autobackup or the switch."""
    _must_not_download(monkeypatch)
    bad = {
        "request": {"vlan_id": 10, "vlan_name": "bad name"},
        "confirm_switch_host": "192.0.2.3",
    }
    r = client.post("/api/v1/vlans", json=bad)
    assert r.status_code == 422
    assert r.json().get("error") == "validation"


def test_rename_vlan_path_id_is_authoritative(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    seen: dict[str, object] = {}

    async def fake_rename(transport: object, *, request: object) -> VlanWriteAck:
        seen["request"] = request
        return VlanWriteAck(ok=True)

    monkeypatch.setattr(vlan_module, "rename_vlan", fake_rename)

    r = client.put("/api/v1/vlans/42/name", json=_REN_BODY)
    assert r.status_code == 200, r.text
    req = seen["request"]
    assert getattr(req, "vlan_id", None) == 42
    assert getattr(req, "vlan_name", None) == "Lab"


def test_set_vlan_ports_path_id_overrides_body(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, *, request: object) -> VlanWriteAck:
        seen["request"] = request
        return VlanWriteAck(ok=True)

    monkeypatch.setattr(vlan_module, "set_vlan_ports", fake_set)

    body = {
        "request": {"vlan_id": 999, "changes": [{"port_id": 3, "mode": 2}]},
        "confirm_switch_host": "192.0.2.3",
    }
    r = client.put("/api/v1/vlans/10/ports", json=body)
    assert r.status_code == 200, r.text
    assert getattr(seen["request"], "vlan_id", None) == 10


def test_delete_vlans_surfaces_switch_error_verbatim(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The firmware rejects e.g. deleting the primary VLAN — its message
    must reach the caller as a 422 operation error, not a generic 500."""
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")

    async def fake_delete(transport: object, **kw: object) -> VlanWriteAck:
        raise OperationError("VLAN 1 is the Primary VLAN and cannot be deleted")

    monkeypatch.setattr(vlan_module, "delete_vlans", fake_delete)

    r = client.post("/api/v1/vlans/delete", json=_DEL_BODY)
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "operation"
    assert "Primary VLAN" in body["detail"]
