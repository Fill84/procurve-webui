"""Tests for /api/v1/status/*.

Strategy: monkeypatch each operation in the router module so transport is
never actually called. Override `get_transport` to a no-op sentinel.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.status as status_module
from app.deps import get_transport
from app.main import create_app
from app.settings import Settings
from procurve_client.models.log import (
    AlertDetail,
    AlertEvent,
    AlertLog,
    DeviceStatusBanner,
)
from procurve_client.models.network import ConfigWriteAck
from procurve_client.models.port import (
    PortCounters,
    PortCountersList,
    PortStatus,
    PortStatusList,
    PortUsage,
    PortUsageList,
)


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


# ---------------------------------------------------------------------------
# Alert detail / ack / delete (Task: alert-log actions)
# ---------------------------------------------------------------------------


def test_get_alert_detail_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    detail = AlertDetail(
        index=1,
        ts_centiseconds=11094915,
        title="Loss of Link",
        severity=3,
        affected_port=10,
        type_code=11,
        act_code=2,
        description="The connection to the devices on port 10 has been lost.",
        solution=["Reattach the cable.", "Troubleshoot the device."],
        other_possibilities="The cable is damaged.",
        raw_html="<html>...</html>",
    )
    captured: dict[str, object] = {}

    async def fake(transport: object, *, index: int, ts_centiseconds: int) -> AlertDetail:
        captured["index"] = index
        captured["ts_centiseconds"] = ts_centiseconds
        return detail

    monkeypatch.setattr(status_module, "get_alert_detail", fake)
    r = client.get("/api/v1/status/alerts/1?dt=11094915")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Loss of Link"
    assert body["severity"] == 3
    assert body["affected_port"] == 10
    assert body["type_code"] == 11
    assert body["act_code"] == 2
    assert body["solution"] == ["Reattach the cable.", "Troubleshoot the device."]
    # The endpoint forwards both query args.
    assert captured["index"] == 1
    assert captured["ts_centiseconds"] == 11094915


def test_get_alert_detail_requires_auth(settings: Settings) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        r = c.get("/api/v1/status/alerts/1?dt=1")
        assert r.status_code == 401


def test_ack_alerts_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    async def fake(transport: object, *, events: list[AlertEvent]) -> ConfigWriteAck:
        captured["events"] = events
        return ConfigWriteAck(ok=True, raw_body="")

    monkeypatch.setattr(status_module, "ack_alerts", fake)
    r = client.post(
        "/api/v1/status/alerts/ack",
        json={
            "events": [
                {"row_id": "1", "ts_centiseconds": 11094915},
                {"row_id": "2", "ts_centiseconds": 12000000},
            ]
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    events = captured["events"]
    assert isinstance(events, list)
    assert len(events) == 2
    assert events[0].row_id == "1"
    assert events[0].ts_centiseconds == 11094915
    assert events[1].row_id == "2"
    assert events[1].ts_centiseconds == 12000000


def test_ack_alerts_blocked_when_read_only(
    read_only_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    called = False

    async def must_not_run(transport: object, *, events: list[AlertEvent]) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(status_module, "ack_alerts", must_not_run)
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        r = c.post(
            "/api/v1/status/alerts/ack",
            json={"events": [{"row_id": "1", "ts_centiseconds": 1}]},
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    body = r.json()
    detail = body  # flat {error, detail} envelope
    assert detail.get("error") == "read_only"
    assert called is False


def test_ack_alerts_requires_auth(settings: Settings) -> None:
    fresh = create_app()
    with TestClient(fresh) as c:
        fresh.state.settings = settings
        r = c.post(
            "/api/v1/status/alerts/ack",
            json={"events": [{"row_id": "1", "ts_centiseconds": 1}]},
        )
        assert r.status_code == 401


def test_ack_alerts_rejects_empty_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The body schema requires `events` to have at least one entry."""

    async def must_not_run(transport: object, *, events: list[AlertEvent]) -> ConfigWriteAck:
        raise AssertionError("op must not run for empty events")

    monkeypatch.setattr(status_module, "ack_alerts", must_not_run)
    r = client.post("/api/v1/status/alerts/ack", json={"events": []})
    assert r.status_code == 422


def test_delete_alerts_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    async def fake(transport: object, *, events: list[AlertEvent]) -> ConfigWriteAck:
        captured["events"] = events
        return ConfigWriteAck(ok=True, raw_body=None)

    monkeypatch.setattr(status_module, "delete_alerts", fake)
    r = client.post(
        "/api/v1/status/alerts/delete",
        json={"events": [{"row_id": "5", "ts_centiseconds": 99}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    events = captured["events"]
    assert isinstance(events, list)
    assert len(events) == 1
    assert events[0].row_id == "5"
    assert events[0].ts_centiseconds == 99


def test_delete_alerts_blocked_when_read_only(
    read_only_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    app.state.settings = read_only_settings
    called = False

    async def must_not_run(transport: object, *, events: list[AlertEvent]) -> ConfigWriteAck:
        nonlocal called
        called = True
        return ConfigWriteAck(ok=True)

    monkeypatch.setattr(status_module, "delete_alerts", must_not_run)
    with TestClient(app) as c:
        app.dependency_overrides[get_transport] = lambda: object()
        r = c.post(
            "/api/v1/status/alerts/delete",
            json={"events": [{"row_id": "1", "ts_centiseconds": 1}]},
        )
        app.dependency_overrides.clear()
    assert r.status_code == 403
    assert called is False
