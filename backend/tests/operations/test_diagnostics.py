"""Unit tests for Diagnostics-tab operations.

Safety:
- device_reset is NEVER live-tested; the test only asserts the URL the
  operation would construct.
- ping / link_test use @WRITE and require READ_ONLY=false; tests set it
  via monkeypatch.
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.operations.diagnostics import (
    device_reset,
    get_configuration_report,
    link_test,
    ping,
)
from procurve_client.transport import ProcurveTransport


# ---- ping ---------------------------------------------------------------

async def test_ping_blocked_when_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await ping(t, destination="192.168.178.3")


@respx.mock
async def test_ping_parses_successes_failures(
    monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    body = (fixtures_dir / "diagnostics__ping.response.txt").read_text(encoding="ascii")
    route = respx.get("http://192.168.178.3/cgi/ping").mock(
        return_value=Response(200, text=body, headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await ping(t, destination="192.168.178.3", packet_count=1, timeout_s=5)
    assert result.successes == 1
    assert result.failures == 0
    assert result.raw_html == body
    # Correct query params.
    p = route.calls.last.request.url.params
    assert p["tp"] == "1"
    assert p["da"] == "192.168.178.3"
    assert p["nr"] == "1"
    assert p["to"] == "5"
    assert p["action"] == "start"


@respx.mock
async def test_ping_raises_on_missing_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get("http://192.168.178.3/cgi/ping").mock(
        return_value=Response(200, text="<html>nope</html>",
                              headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await ping(t, destination="1.2.3.4")


# ---- link_test ----------------------------------------------------------

async def test_link_test_blocked_when_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await link_test(t, destination="00-1b-44-11-3a-b7")


@respx.mock
async def test_link_test_sends_tp_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """No live fixture exists for link_test; use a minimal synthetic response."""
    monkeypatch.setenv("READ_ONLY", "false")
    synthetic = (
        "<html><body>"
        "<th>Successes: 0</th><th>Failures: 20</th>"
        "</body></html>"
    )
    route = respx.get("http://192.168.178.3/cgi/ping").mock(
        return_value=Response(200, text=synthetic, headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await link_test(t, destination="00-1b-44-11-3a-b7", packet_count=10)
    assert result.successes == 0
    assert result.failures == 20
    p = route.calls.last.request.url.params
    assert p["tp"] == "2"
    assert p["da"] == "00-1b-44-11-3a-b7"
    assert p["nr"] == "10"


# ---- get_configuration_report ------------------------------------------

@respx.mock
async def test_get_configuration_report_parses_pre_block(fixtures_dir: Path) -> None:
    body = (
        fixtures_dir / "diagnostics__get_configuration_report.response.txt"
    ).read_text(encoding="ascii")
    respx.get("http://192.168.178.3/diagnostics/config.html").mock(
        return_value=Response(200, text=body, headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        report = await get_configuration_report(t)
    assert report.raw_html == body
    assert report.config_text.startswith(
        "; J9021A Configuration Editor; Created on release #N.11.78"
    )
    assert 'hostname "HP2810_01"' in report.config_text
    # Structured parse from the shared helper
    assert report.running_config.hostname == "HP2810_01"
    assert report.running_config.firmware == "N.11.78"


@respx.mock
async def test_get_configuration_report_raises_on_missing_pre() -> None:
    respx.get("http://192.168.178.3/diagnostics/config.html").mock(
        return_value=Response(200, text="<html>no pre here</html>",
                              headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_configuration_report(t)


# ---- device_reset (FORBIDDEN — URL verification only) -------------------

async def test_device_reset_blocked_when_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The write-safety decorator must refuse this op by default."""
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await device_reset(t)


@respx.mock
async def test_device_reset_constructs_correct_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify URL only. Never live-tested."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/device_reset").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await device_reset(t)
    assert route.called
    assert str(route.calls.last.request.url) == "http://192.168.178.3/cgi/device_reset"
    assert result.initiated is True
