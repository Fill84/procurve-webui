"""Unit tests for Status-tab operations.

All five endpoints return bare-row tilde-delimited streams (no OK~ sentinel).
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError
from procurve_client.operations.status import (
    get_alert_log,
    get_device_status,
    get_port_counters,
    get_port_status,
    get_port_usage,
)
from procurve_client.transport import ProcurveTransport


def _read_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="ascii")


# ---- get_device_status --------------------------------------------------

@respx.mock
async def test_get_device_status_parses_first_line(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_device_status.response.txt")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        status = await get_device_status(t)
    assert route.called
    assert route.calls.last.request.url.params["action"] == "status"
    # Applet consumes only line 1: "2842990~1"
    assert status.state == "2842990"
    assert status.index == "1"
    assert status.description is None
    assert status.ts_centiseconds is None


@respx.mock
async def test_get_device_status_full_4_fields() -> None:
    """When the switch emits a 4-field banner line, all fields are populated."""
    respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="1~42~% something went wrong~12345\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        status = await get_device_status(t)
    assert status.state == "1"
    assert status.index == "42"
    # Leading "% " must be stripped per DeviceStatus.java:182-184.
    assert status.description == "something went wrong"
    assert status.ts_centiseconds == 12345


@respx.mock
async def test_get_device_status_empty_body_raises() -> None:
    respx.get("http://192.0.2.3/cgi/fflog").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_device_status(t)


# ---- get_alert_log ------------------------------------------------------

@respx.mock
async def test_get_alert_log_parses_meta_plus_rows(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_alert_log.response.txt")
    route = respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        log = await get_alert_log(t)
    assert route.calls.last.request.url.params["action"] == "list"
    assert log.latest_ts_centiseconds == 2842990
    assert log.cursor_or_count == 1
    assert len(log.events) == 1
    e = log.events[0]
    assert e.row_id == "1"
    assert e.alert_name == "10 3"
    assert e.category == "Loss of link"
    assert e.ts_centiseconds == 3644720
    assert "Lost connection" in e.description


@respx.mock
async def test_get_alert_log_empty_when_only_meta_line() -> None:
    respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="0~0\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        log = await get_alert_log(t)
    assert log.latest_ts_centiseconds == 0
    assert log.cursor_or_count == 0
    assert log.events == []


@respx.mock
async def test_get_alert_log_malformed_row_raises() -> None:
    respx.get("http://192.0.2.3/cgi/fflog").mock(
        return_value=Response(200, text="0~0\nonly-three~fields~here\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_alert_log(t)


# ---- get_port_status ----------------------------------------------------

@respx.mock
async def test_get_port_status_parses_all_24_ports(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_port_status.response.txt")
    respx.get("http://192.0.2.3/cgi/get_ports").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        ports = await get_port_status(t)
    assert len(ports.ports) == 24
    p1 = ports.ports[0]
    assert p1.port == 1
    assert p1.port_name == "1-Dyn1"
    assert p1.port_type_label == " "
    assert p1.port_type == "100/1000T"
    assert p1.enabled is True
    assert p1.link_status == "Up"
    assert p1.current_mode == "1000FDx"
    assert p1.flow_ctrl == "on(Tx+Rx)"
    assert p1.extra == 0

    # Port 18 has port_type_label "UPS"
    p18 = ports.ports[17]
    assert p18.port == 18
    assert p18.port_type_label == "UPS"
    assert p18.current_mode == "100FDx"

    # Port 23 is administratively disabled and down
    p23 = ports.ports[22]
    assert p23.enabled is False
    assert p23.link_status == "Down"
    assert p23.flow_ctrl == "off"


@respx.mock
async def test_get_port_status_raises_on_short_row() -> None:
    respx.get("http://192.0.2.3/cgi/get_ports").mock(
        return_value=Response(200, text="1~name~ ~type~Yes~Up\n")  # only 6 fields
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_port_status(t)


# ---- get_port_counters --------------------------------------------------

@respx.mock
async def test_get_port_counters_parses_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_port_counters.response.txt")
    respx.get("http://192.0.2.3/cgi/portc").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        counters = await get_port_counters(t)
    assert len(counters.ports) == 24
    p1 = counters.ports[0]
    assert p1.port == 1
    assert p1.port_name == "1-Dyn1"
    assert p1.mcast_rx == 1220
    assert p1.mcast_tx == 39709
    assert p1.bcast_rx == 65
    assert p1.bcast_tx == 183
    assert p1.pkts_rx == 57659
    assert p1.pkts_tx == 2174938
    assert p1.errors_rx == 0

    p18 = counters.ports[17]
    assert p18.port == 18
    assert p18.port_type_label == "UPS"
    assert p18.pkts_tx == 61427

    # A port that is down has zero counters in the capture
    p11 = counters.ports[10]
    assert p11.port == 11
    assert all(
        v == 0 for v in (
            p11.mcast_rx, p11.mcast_tx, p11.bcast_rx, p11.bcast_tx,
            p11.pkts_rx, p11.pkts_tx, p11.errors_rx,
        )
    )


# ---- get_port_usage -----------------------------------------------------

@respx.mock
async def test_get_port_usage_parses_fixture(fixtures_dir: Path) -> None:
    """The live fixture has the 7-field (with speed) layout."""
    body = _read_fixture(fixtures_dir, "get_port_usage.response.txt")
    route = respx.get("http://192.0.2.3/cgi/port_usage").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        usage = await get_port_usage(t)
    assert route.calls.last.request.url.params["LAST_PORT"] == "0"
    assert route.calls.last.request.url.params["NUM_PORTS"] == "-1"
    assert len(usage.ports) == 24
    p1 = usage.ports[0]
    assert p1.port == 1
    assert p1.label == "1"
    assert p1.state == "G"
    assert p1.usage1 == p1.usage2 == p1.usage3 == 0
    assert p1.speed == "1Gbs"
    assert p1.total_usage_pct == 0

    p18 = usage.ports[17]
    assert p18.speed == "100Mbs"
    p23 = usage.ports[22]
    assert p23.state == "N"


@respx.mock
async def test_get_port_usage_cursor_params() -> None:
    route = respx.get("http://192.0.2.3/cgi/port_usage").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        usage = await get_port_usage(t, last_port=24, num_ports=26)
    assert usage.ports == []
    assert route.calls.last.request.url.params["LAST_PORT"] == "24"
    assert route.calls.last.request.url.params["NUM_PORTS"] == "26"


@respx.mock
async def test_get_port_usage_accepts_6_field_row_without_speed() -> None:
    """PortGraph.java:919 makes `speed` optional. Handle 6-field rows too."""
    # Synthetic: 6 fields per row, no speed. `# TODO: needs live capture` to
    # confirm this shape ever appears — defensive support for the applet's
    # documented hasMoreTokens() check.
    body = "1~1~G~10~20~30\n2~2~W~0~0~0\n"
    respx.get("http://192.0.2.3/cgi/port_usage").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        usage = await get_port_usage(t)
    assert len(usage.ports) == 2
    assert usage.ports[0].speed is None
    assert usage.ports[0].total_usage_pct == 60
    assert usage.ports[1].state == "W"


@respx.mock
async def test_get_port_usage_rejects_bad_state() -> None:
    respx.get("http://192.0.2.3/cgi/port_usage").mock(
        return_value=Response(200, text="1~1~X~0~0~0~1Gbs\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_port_usage(t)
