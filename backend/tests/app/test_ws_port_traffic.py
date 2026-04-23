"""Tests for the /ws/port-traffic WebSocket endpoint (Task 2.5).

We mock ``app.ws.port_traffic.get_port_counters`` directly rather than
mocking the /cgi/portc wire responses — the wire parser already has its own
coverage, and faking the operation lets us drive counter values (including
wrap cases) without constructing tilde-delimited fixtures for every test.

Auth tests construct a real session via the login flow, matching the
pattern used by test_auth_flow.py.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from starlette.websockets import WebSocketDisconnect

import app.ws.port_traffic as port_traffic_module
from app import auth as auth_module
from app.main import create_app
from app.settings import Settings
from procurve_client.models.port import PortCounters, PortCountersList


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SWITCH_HOST", "192.168.178.3")
    monkeypatch.setenv("SWITCH_PORT", "80")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    # Snappy poll interval so tests can observe two frames in <1s.
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "0.05")
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    a = create_app()
    a.state.settings = settings
    return a


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        # lifespan already built settings from env; pin the fixture instance
        # so settings.poll_interval_seconds is what the WS handler reads.
        app.state.settings = settings_from_app(app)
        yield c


def settings_from_app(app: FastAPI) -> Settings:
    return app.state.settings  # type: ignore[no-any-return]


def _mock_probe_ok() -> respx.Route:
    return respx.get("http://192.168.178.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>"),
    )


def _login(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert resp.status_code == 200, resp.text


def _counters(
    port: int,
    *,
    pkts_rx: int = 0,
    pkts_tx: int = 0,
    mcast_rx: int = 0,
    mcast_tx: int = 0,
    bcast_rx: int = 0,
    bcast_tx: int = 0,
    errors_rx: int = 0,
) -> PortCounters:
    return PortCounters(
        port=port,
        port_name="",
        port_type_label="",
        mcast_rx=mcast_rx,
        mcast_tx=mcast_tx,
        bcast_rx=bcast_rx,
        bcast_tx=bcast_tx,
        pkts_rx=pkts_rx,
        pkts_tx=pkts_tx,
        errors_rx=errors_rx,
    )


# ---------------------------------------------------------------------------
# Auth rejection paths — must close without emitting any frame.
# ---------------------------------------------------------------------------


def test_ws_rejects_missing_session_cookie(client: TestClient) -> None:
    """No cookie at all → handshake accepted then closed with 1008."""
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/ws/port-traffic") as ws,
    ):
        # Should close before we can receive anything.
        ws.receive_json()
    assert excinfo.value.code == 1008


def test_ws_rejects_bad_session_cookie(client: TestClient) -> None:
    """Garbage signed value → 1008. TestClient lets us set arbitrary cookies."""
    client.cookies.set("session", "not-a-valid-signed-token")
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/ws/port-traffic") as ws,
    ):
        ws.receive_json()
    assert excinfo.value.code == 1008


@respx.mock
def test_ws_rejects_expired_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session past its expiry must be rejected at connect."""
    _mock_probe_ok()
    t0 = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(auth_module, "_now", lambda: t0)
    _login(client)
    # Jump past TTL.
    monkeypatch.setattr(auth_module, "_now", lambda: t0 + timedelta(hours=9))
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/ws/port-traffic") as ws,
    ):
        ws.receive_json()
    assert excinfo.value.code == 1008


# ---------------------------------------------------------------------------
# Happy-path framing.
# ---------------------------------------------------------------------------


@respx.mock
def test_ws_emits_frame_with_rates_after_second_poll(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second poll yields real per-second rates relative to the first snapshot."""
    _mock_probe_ok()
    _login(client)

    snapshots = [
        PortCountersList(
            ports=[
                _counters(1, pkts_rx=100, pkts_tx=50, bcast_rx=1),
                _counters(2, pkts_rx=0, pkts_tx=0),
            ]
        ),
        PortCountersList(
            ports=[
                _counters(1, pkts_rx=200, pkts_tx=100, bcast_rx=3),
                _counters(2, pkts_rx=10, pkts_tx=5),
            ]
        ),
    ]
    call_n = {"i": 0}

    async def fake_counters(_transport: object) -> PortCountersList:
        i = call_n["i"]
        call_n["i"] = min(i + 1, len(snapshots) - 1)
        return snapshots[i]

    # Pin clock so dt is exactly 1 second between frames.
    times = iter(
        [
            datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 4, 23, 12, 0, 1, tzinfo=UTC),
            datetime(2026, 4, 23, 12, 0, 2, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(auth_module, "_now", lambda: next(times))
    monkeypatch.setattr(port_traffic_module, "get_port_counters", fake_counters)

    with client.websocket_connect("/ws/port-traffic") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert first["ports"] == []  # no baseline yet
    assert "timestamp" in first
    assert first["poll_interval_s"] == 0.05
    by_port = {p["port"]: p for p in second["ports"]}
    assert by_port[1]["pkts_in_per_s"] == pytest.approx(100.0)
    assert by_port[1]["pkts_out_per_s"] == pytest.approx(50.0)
    assert by_port[1]["bcast_in_per_s"] == pytest.approx(2.0)
    assert by_port[2]["pkts_in_per_s"] == pytest.approx(10.0)


@respx.mock
def test_ws_handles_counter_wrap(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prev=2^32-10, curr=5 → delta 15, rate 15/dt (dt=1s → 15.0)."""
    _mock_probe_ok()
    _login(client)

    wrap = 2**32
    snapshots = [
        PortCountersList(ports=[_counters(1, pkts_rx=wrap - 10)]),
        PortCountersList(ports=[_counters(1, pkts_rx=5)]),
    ]
    call_n = {"i": 0}

    async def fake_counters(_transport: object) -> PortCountersList:
        i = call_n["i"]
        call_n["i"] = min(i + 1, len(snapshots) - 1)
        return snapshots[i]

    times = iter(
        [
            datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 4, 23, 12, 0, 1, tzinfo=UTC),
            datetime(2026, 4, 23, 12, 0, 2, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(auth_module, "_now", lambda: next(times))
    monkeypatch.setattr(port_traffic_module, "get_port_counters", fake_counters)

    with client.websocket_connect("/ws/port-traffic") as ws:
        ws.receive_json()  # empty
        second = ws.receive_json()

    assert second["ports"][0]["pkts_in_per_s"] == pytest.approx(15.0)


@respx.mock
def test_ws_uses_configured_poll_interval(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`poll_interval_s` in every frame matches settings.poll_interval_seconds."""
    _mock_probe_ok()
    _login(client)

    async def fake_counters(_transport: object) -> PortCountersList:
        return PortCountersList(ports=[_counters(1, pkts_rx=1)])

    monkeypatch.setattr(port_traffic_module, "get_port_counters", fake_counters)

    with client.websocket_connect("/ws/port-traffic") as ws:
        frame = ws.receive_json()
        assert frame["poll_interval_s"] == 0.05


@respx.mock
def test_ws_first_frame_has_no_fake_rates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First poll has no previous snapshot — emit empty ports list, no zeros."""
    _mock_probe_ok()
    _login(client)

    async def fake_counters(_transport: object) -> PortCountersList:
        return PortCountersList(
            ports=[_counters(1, pkts_rx=999), _counters(2, pkts_rx=1)]
        )

    monkeypatch.setattr(port_traffic_module, "get_port_counters", fake_counters)

    with client.websocket_connect("/ws/port-traffic") as ws:
        frame = ws.receive_json()

    assert frame["ports"] == []
