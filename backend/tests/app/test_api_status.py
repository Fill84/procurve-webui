"""Tests for /api/v1/status/*.

Strategy: monkeypatch each operation in the router module so transport is
never actually called. Override `get_transport` to a no-op sentinel.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.status as status_module
from app.deps import get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.log import AlertEvent, AlertLog, DeviceStatusBanner
from procurve_client.models.port import (
    PortCounters,
    PortCountersList,
    PortStatus,
    PortStatusList,
    PortUsage,
    PortUsageList,
)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    a = create_app()
    a.state.settings = settings
    return a


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        try:
            yield c
        finally:
            app.dependency_overrides.clear()


def test_get_device_status_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    banner = DeviceStatusBanner(
        state="Normal", index=None, description=None, ts_centiseconds=None
    )

    async def fake(transport: object) -> DeviceStatusBanner:
        return banner

    monkeypatch.setattr(status_module, "get_device_status", fake)
    r = client.get("/api/v1/status/device")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "Normal"


def test_get_port_status_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    ports = PortStatusList(
        ports=[
            PortStatus(
                port=1,
                port_name="",
                port_type_label="",
                port_type="100/1000T",
                enabled=True,
                link_status="Up",
                current_mode="1000FDx",
                trunk="",
                flow_ctrl="off",
                extra=0,
            ),
        ]
    )

    async def fake(transport: object) -> PortStatusList:
        return ports

    monkeypatch.setattr(status_module, "get_port_status", fake)
    r = client.get("/api/v1/status/ports")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ports"]) == 1
    assert body["ports"][0]["port"] == 1
    assert body["ports"][0]["link_status"] == "Up"


def test_get_port_counters_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    counters = PortCountersList(
        ports=[
            PortCounters(
                port=1,
                port_name="",
                port_type_label="",
                mcast_rx=0,
                mcast_tx=0,
                bcast_rx=0,
                bcast_tx=0,
                pkts_rx=42,
                pkts_tx=17,
                errors_rx=0,
            ),
        ]
    )

    async def fake(transport: object) -> PortCountersList:
        return counters

    monkeypatch.setattr(status_module, "get_port_counters", fake)
    r = client.get("/api/v1/status/counters")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ports"][0]["pkts_rx"] == 42
    assert body["ports"][0]["pkts_tx"] == 17


def test_get_alert_log_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = AlertLog(
        latest_ts_centiseconds=123,
        cursor_or_count=1,
        events=[
            AlertEvent(
                row_id="1",
                alert_name="cold-start",
                category="system",
                ts_centiseconds=100,
                description="Device restarted",
            )
        ],
    )

    async def fake(transport: object) -> AlertLog:
        return log

    monkeypatch.setattr(status_module, "get_alert_log", fake)
    r = client.get("/api/v1/status/alert-log")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cursor_or_count"] == 1
    assert body["events"][0]["alert_name"] == "cold-start"


def test_get_port_usage_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage = PortUsageList(
        ports=[
            PortUsage(
                port=1,
                label="",
                state="G",
                usage1=10,
                usage2=5,
                usage3=0,
                speed="1000",
            ),
            PortUsage(
                port=2,
                label="",
                state="N",
                usage1=0,
                usage2=0,
                usage3=0,
                speed=None,
            ),
        ]
    )

    async def fake(transport: object) -> PortUsageList:
        return usage

    monkeypatch.setattr(status_module, "get_port_usage", fake)
    r = client.get("/api/v1/status/port-usage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ports"]) == 2
    assert body["ports"][0]["usage1"] == 10
    assert body["ports"][0]["state"] == "G"


def test_status_requires_auth(settings: Settings) -> None:
    """One 401 check covers the whole router — all endpoints use get_transport."""
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        # No dependency override -> get_transport runs and requires a session
        r = c.get("/api/v1/status/device")
        assert r.status_code == 401
