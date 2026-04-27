"""Tests for /api/v1/security/* (Task 3.4).

Strategy:
  * Patch the procurve_client operation functions on the security router
    module with async fakes. No test invokes the live switch.
  * For writes, patch ``download_config`` on the ``write_safety`` module so
    the autobackup step doesn't attempt switch I/O either.
  * Override ``get_transport`` with a sentinel object and ``get_backup_store``
    with a fresh store rooted at ``tmp_path``.

SAFETY INVARIANTS VERIFIED HERE
-------------------------------
- Lockout-risky writes (web-access, web-managers) require
  ``confirm_switch_host`` matching ``settings.switch_host``.
- Per-port + intrusion-reset writes do NOT require host confirmation.
- All four writes go through ``write_with_autobackup`` (pre-write
  backup appears on disk before the op runs).
- ``PUT /api/v1/security/device-passwords`` is the most lockout-risky
  write of the three: a wrong Manager password is recoverable only via
  a physical factory-reset. It carries the same gates as the other two
  lockout-risky writes (host-confirm + pre-write autobackup + READ_ONLY
  guard) plus loud UI warnings about the cleartext-in-URL firmware flaw.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.security as security_module
from app import write_safety
from app.backup_store import BackupStore
from app.deps import get_backup_store, get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.backup import ConfigBackup
from procurve_client.models.security import (
    AccessLevel,
    AuthorizedManager,
    CertMode,
    IntrusionEntry,
    IntrusionLogResponse,
    PerportsResponse,
    PortSecurityRow,
    ResetIntrusionFlagsResponse,
    SetDevicePasswordsResponse,
    SetPerportResponse,
    SetSSLResponse,
    SetWebManagerResponse,
    SSLState,
    WebAccessPage,
    WebManagersResponse,
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


def _install_download_config(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    fake = ConfigBackup.from_bytes(payload)

    async def fake_download(transport: object) -> ConfigBackup:
        return fake

    monkeypatch.setattr(write_safety, "download_config", fake_download)


def _must_not_download(monkeypatch: pytest.MonkeyPatch) -> None:
    async def blow_up(transport: object) -> ConfigBackup:
        raise AssertionError("download_config should not run")

    monkeypatch.setattr(write_safety, "download_config", blow_up)


# ---------------------------------------------------------------------------
# Web access (read)
# ---------------------------------------------------------------------------


def test_web_access_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> WebAccessPage:
        return WebAccessPage(operator_username="", manager_username="")

    monkeypatch.setattr(security_module, "get_web_access_page", fake_get)
    r = client.get("/api/v1/security/web-access")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["operator_username"] == ""
    assert body["manager_username"] == ""


def test_web_access_read_requires_auth(
    settings: Settings, store: BackupStore
) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        fresh.state.backup_store = store
        r = c.get("/api/v1/security/web-access")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Web access (write — lockout-risky: host confirmation + autobackup)
# ---------------------------------------------------------------------------


_SSL_REQUEST_BODY = {
    "request": {
        "enabled": 2,
        "port": 443,
        "cert_mode": 2,
    },
    "confirm_switch_host": "192.0.2.3",
}


def test_web_access_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object, **kw: object) -> SetSSLResponse:
        nonlocal called
        called = True
        return SetSSLResponse(applied=True)

    monkeypatch.setattr(security_module, "set_ssl", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/security/web-access", json=_SSL_REQUEST_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "read_only"
    assert called is False


def test_web_access_write_requires_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def must_not_run(transport: object, **kw: object) -> SetSSLResponse:
        nonlocal called
        called = True
        return SetSSLResponse(applied=True)

    monkeypatch.setattr(security_module, "set_ssl", must_not_run)
    _must_not_download(monkeypatch)

    bad = {**_SSL_REQUEST_BODY, "confirm_switch_host": "10.0.0.1"}
    r = client.put("/api/v1/security/web-access", json=bad)
    assert r.status_code == 400
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "host_mismatch"
    assert called is False


def test_web_access_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_set(transport: object, **kw: object) -> SetSSLResponse:
        order.append("set_ssl")
        return SetSSLResponse(applied=True)

    monkeypatch.setattr(security_module, "set_ssl", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/security/web-access", json=_SSL_REQUEST_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_ssl"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_web_access_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"running-config\n")

    async def fake_set(transport: object, **kw: object) -> SetSSLResponse:
        return SetSSLResponse(applied=True, message="ok")

    monkeypatch.setattr(security_module, "set_ssl", fake_set)
    r = client.put("/api/v1/security/web-access", json=_SSL_REQUEST_BODY)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] is True
    assert body["message"] == "ok"


# ---------------------------------------------------------------------------
# Web managers (read + write)
# ---------------------------------------------------------------------------


def test_web_managers_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> WebManagersResponse:
        return WebManagersResponse(
            entries=[
                AuthorizedManager(
                    index=1,
                    ip="192.168.178.100",
                    mask="255.255.255.255",
                    access_level=AccessLevel.MANAGER,
                ),
            ]
        )

    monkeypatch.setattr(security_module, "get_web_managers", fake_get)
    r = client.get("/api/v1/security/web-managers")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["ip"] == "192.168.178.100"
    assert body["entries"][0]["access_level"] == "Manager"


_WEB_MGR_ADD_BODY = {
    "request": {
        "action": 1,
        "ip": "192.168.178.100",
        "mask": "255.255.255.255",
        "level": 2,
        "indeces": [],
    },
    "confirm_switch_host": "192.0.2.3",
}


def test_web_managers_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(
        transport: object, **kw: object
    ) -> SetWebManagerResponse:
        nonlocal called
        called = True
        return SetWebManagerResponse(applied=True)

    monkeypatch.setattr(security_module, "set_web_manager", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.post("/api/v1/security/web-managers", json=_WEB_MGR_ADD_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_web_managers_write_requires_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def must_not_run(
        transport: object, **kw: object
    ) -> SetWebManagerResponse:
        nonlocal called
        called = True
        return SetWebManagerResponse(applied=True)

    monkeypatch.setattr(security_module, "set_web_manager", must_not_run)
    _must_not_download(monkeypatch)

    bad = {**_WEB_MGR_ADD_BODY, "confirm_switch_host": "wrong"}
    r = client.post("/api/v1/security/web-managers", json=bad)
    assert r.status_code == 400
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "host_mismatch"
    assert called is False


def test_web_managers_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_set(
        transport: object, **kw: object
    ) -> SetWebManagerResponse:
        order.append("set_web_manager")
        return SetWebManagerResponse(applied=True)

    monkeypatch.setattr(security_module, "set_web_manager", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.post("/api/v1/security/web-managers", json=_WEB_MGR_ADD_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_web_manager"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_web_managers_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(
        transport: object, **kw: object
    ) -> SetWebManagerResponse:
        return SetWebManagerResponse(applied=True)

    monkeypatch.setattr(security_module, "set_web_manager", fake_set)
    r = client.post("/api/v1/security/web-managers", json=_WEB_MGR_ADD_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True


# ---------------------------------------------------------------------------
# Per-port (read + write — no host confirmation)
# ---------------------------------------------------------------------------


def test_per_port_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(
        transport: object, *, group: str = ""
    ) -> PerportsResponse:
        assert group == ""
        return PerportsResponse(
            rows=[
                PortSecurityRow(
                    port=7,
                    port_label="7",
                    port_name=" ",
                    address_selection="Continuous",
                    authorized_address=" ",
                    mode="None",
                    security_action=1,
                    address_limit=1,
                    trunk=False,
                )
            ]
        )

    monkeypatch.setattr(security_module, "get_perports", fake_get)
    r = client.get("/api/v1/security/per-port")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["port"] == 7


_PERPORT_BODY = {
    "request": {
        "group": "",
        "trunk": 0,
        "port": 7,
        "indeces": [7],
        "mode": 1,
        "security_action": 1,
        "address_limit": 1,
    }
}


def test_per_port_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(
        transport: object, **kw: object
    ) -> SetPerportResponse:
        nonlocal called
        called = True
        return SetPerportResponse(applied=True)

    monkeypatch.setattr(security_module, "set_perport", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put("/api/v1/security/per-port/7", json=_PERPORT_BODY)
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_per_port_write_does_not_require_host_confirmation(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Body WITHOUT ``confirm_switch_host`` should be accepted — per-port
    writes are not lockout-risky."""
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(
        transport: object, **kw: object
    ) -> SetPerportResponse:
        return SetPerportResponse(applied=True)

    monkeypatch.setattr(security_module, "set_perport", fake_set)
    r = client.put("/api/v1/security/per-port/7", json=_PERPORT_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True


def test_per_port_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_set(
        transport: object, **kw: object
    ) -> SetPerportResponse:
        order.append("set_perport")
        return SetPerportResponse(applied=True)

    monkeypatch.setattr(security_module, "set_perport", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put("/api/v1/security/per-port/7", json=_PERPORT_BODY)
    assert r.status_code == 200, r.text
    assert order == ["save", "set_perport"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_per_port_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    seen: dict[str, object] = {}

    async def fake_set(transport: object, **kw: object) -> SetPerportResponse:
        seen.update(kw)
        return SetPerportResponse(applied=True)

    monkeypatch.setattr(security_module, "set_perport", fake_set)
    # Use port=9 in the URL even though the body says port=7 — route wins.
    body = {"request": {**_PERPORT_BODY["request"], "port": 7}}
    r = client.put("/api/v1/security/per-port/9", json=body)
    assert r.status_code == 200, r.text
    # Route param overrides body port (9, not 7).
    req = seen["request"]
    assert req.port == 9  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Intrusion log (read + reset — no host confirmation)
# ---------------------------------------------------------------------------


def test_intrusion_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> IntrusionLogResponse:
        return IntrusionLogResponse(
            entries=[
                IntrusionEntry(
                    port=3,
                    port_name="lab",
                    intruder_address="aa-bb-cc-dd-ee-ff",
                    timestamp="2024-01-01 12:00:00",
                )
            ]
        )

    monkeypatch.setattr(security_module, "get_intrusion", fake_get)
    r = client.get("/api/v1/security/intrusion")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["entries"]) == 1


def test_intrusion_reset_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(transport: object) -> ResetIntrusionFlagsResponse:
        nonlocal called
        called = True
        return ResetIntrusionFlagsResponse(applied=True)

    monkeypatch.setattr(security_module, "reset_intrusion_flags", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.post("/api/v1/security/intrusion/reset")
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False


def test_intrusion_reset_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")
    order: list[str] = []

    async def fake_reset(transport: object) -> ResetIntrusionFlagsResponse:
        order.append("reset")
        return ResetIntrusionFlagsResponse(applied=True)

    monkeypatch.setattr(security_module, "reset_intrusion_flags", fake_reset)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.post("/api/v1/security/intrusion/reset")
    assert r.status_code == 200, r.text
    assert order == ["save", "reset"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_intrusion_reset_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_reset(transport: object) -> ResetIntrusionFlagsResponse:
        return ResetIntrusionFlagsResponse(applied=True)

    monkeypatch.setattr(security_module, "reset_intrusion_flags", fake_reset)
    r = client.post("/api/v1/security/intrusion/reset")
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True


# ---------------------------------------------------------------------------
# SSL state (read)
# ---------------------------------------------------------------------------


def test_ssl_state_read_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get(transport: object) -> SSLState:
        return SSLState(
            ssl_enabled=False,
            ssl_port=443,
            cert_mode=CertMode.USE_INSTALLED,
            ca_signed_installed=False,
        )

    monkeypatch.setattr(security_module, "get_ssl_state", fake_get)
    r = client.get("/api/v1/security/ssl-state")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ssl_enabled"] is False
    assert body["ssl_port"] == 443
    assert body["ca_signed_installed"] is False


# ---------------------------------------------------------------------------
# Device passwords (write — most lockout-risky: host confirmation + autobackup)
# ---------------------------------------------------------------------------


_DEVICE_PASSWORDS_BODY = {
    "request": {
        "operator_username": "operator",
        "operator_password": "op-secret",
        "manager_username": "manager",
        "manager_password": "mgr-secret",
    },
    "confirm_switch_host": "192.0.2.3",
}


def test_device_passwords_write_blocked_when_read_only(
    read_only_settings: Settings,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    app.state.backup_store = store
    called = False

    async def must_not_run(
        transport: object, **kw: object
    ) -> SetDevicePasswordsResponse:
        nonlocal called
        called = True
        return SetDevicePasswordsResponse(applied=True)

    monkeypatch.setattr(security_module, "set_device_passwords", must_not_run)
    _must_not_download(monkeypatch)

    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        app.dependency_overrides[get_backup_store] = lambda: store
        r = c.put(
            "/api/v1/security/device-passwords", json=_DEVICE_PASSWORDS_BODY
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "read_only"
    assert called is False


def test_device_passwords_write_requires_host_confirmation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def must_not_run(
        transport: object, **kw: object
    ) -> SetDevicePasswordsResponse:
        nonlocal called
        called = True
        return SetDevicePasswordsResponse(applied=True)

    monkeypatch.setattr(security_module, "set_device_passwords", must_not_run)
    _must_not_download(monkeypatch)

    bad = {**_DEVICE_PASSWORDS_BODY, "confirm_switch_host": "10.0.0.1"}
    r = client.put("/api/v1/security/device-passwords", json=bad)
    assert r.status_code == 400
    detail = r.json().get("detail", r.json())
    assert detail.get("error") == "host_mismatch"
    assert called is False


def test_device_passwords_write_creates_pre_write_backup(
    client: TestClient,
    store: BackupStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_download_config(monkeypatch, b"hostname HP2810_01\n")
    order: list[str] = []

    async def fake_set(
        transport: object, **kw: object
    ) -> SetDevicePasswordsResponse:
        order.append("set_device_passwords")
        return SetDevicePasswordsResponse(applied=True)

    monkeypatch.setattr(security_module, "set_device_passwords", fake_set)

    original_save = store.save

    def spy_save(*args: object, **kwargs: object) -> object:
        order.append("save")
        return original_save(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(store, "save", spy_save)

    r = client.put(
        "/api/v1/security/device-passwords", json=_DEVICE_PASSWORDS_BODY
    )
    assert r.status_code == 200, r.text
    assert order == ["save", "set_device_passwords"]
    listed = store.list()
    assert len(listed) == 1
    assert listed[0].trigger == "pre-write"


def test_device_passwords_write_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(
        transport: object, **kw: object
    ) -> SetDevicePasswordsResponse:
        return SetDevicePasswordsResponse(applied=True)

    monkeypatch.setattr(security_module, "set_device_passwords", fake_set)
    r = client.put(
        "/api/v1/security/device-passwords", json=_DEVICE_PASSWORDS_BODY
    )
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is True


def test_device_passwords_write_secret_not_in_response_repr(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``SecretStr`` wrapping in the request model means stringifying
    the request never leaks the password. This is a sanity check that
    the API response itself does not echo the cleartext back either.
    """
    _install_download_config(monkeypatch, b"cfg\n")

    async def fake_set(
        transport: object, **kw: object
    ) -> SetDevicePasswordsResponse:
        return SetDevicePasswordsResponse(applied=True, raw_body=None)

    monkeypatch.setattr(security_module, "set_device_passwords", fake_set)
    r = client.put(
        "/api/v1/security/device-passwords", json=_DEVICE_PASSWORDS_BODY
    )
    assert r.status_code == 200, r.text
    assert "op-secret" not in r.text
    assert "mgr-secret" not in r.text
