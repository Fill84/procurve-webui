"""Tests for Configuration → Monitor operations.

- get_monitor_page: scrape monitor1.html
- set_monitor:      /cgi/set_monitor?portCopyStatus=...&portCopyDest=...
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import SetMonitorRequest
from procurve_client.operations.configuration import (
    get_monitor_page,
    monitor_source_mask,
    set_monitor,
)
from procurve_client.transport import ProcurveTransport


def _load_mirror(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "research" / "mirror" / "2026-04-23" / "configuration" / name
    return path.read_text(encoding="utf-8")


@respx.mock
async def test_get_monitor_page_parses_mirror() -> None:
    respx.get("http://192.0.2.3/configuration/monitor1.html").mock(
        return_value=Response(200, text=_load_mirror("monitor1.html"))
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_monitor_page(t)
    # probeStatus = 2 in the mirror → monitoring off.
    assert page.enabled is False
    # The <Select monitoringPort> lists 14 candidate ports on the 2810.
    assert 7 in page.candidate_dest_ports
    assert 24 in page.candidate_dest_ports
    # Port 24 is marked `selected` in the mirror.
    assert page.selected_dest_port == 24


@respx.mock
async def test_get_monitor_page_missing_probe_status_raises() -> None:
    respx.get("http://192.0.2.3/configuration/monitor1.html").mock(
        return_value=Response(200, text="<html>no probeStatus here</html>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_monitor_page(t)


@respx.mock
async def test_set_monitor_disable_emits_status_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/set_monitor").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_monitor(t, request=SetMonitorRequest(enabled=False))
    q = route.calls.last.request.url.params
    assert q["portCopyStatus"] == "2"
    assert "portCopyDest" not in q
    assert "portCopySourceMask" not in q


@respx.mock
async def test_set_monitor_enable_emits_status_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/set_monitor").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_monitor(
            t,
            request=SetMonitorRequest(
                enabled=True, dest_port=24, source_ports=[1, 2]
            ),
        )
    q = route.calls.last.request.url.params
    assert q["portCopyStatus"] == "4"
    assert q["portCopyDest"] == "24"
    # MonitorList.java getPortMask(): port 1 = MSB of a 32-bit word,
    # rendered as zero-padded lowercase hex byte pairs joined by spaces.
    assert q["portCopySourceMask"] == "c0 00 00 00"


@respx.mock
async def test_set_monitor_enable_mask_spaces_encode_as_plus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The applet submits via a browser form → spaces go out as `+`."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/set_monitor").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_monitor(
            t,
            request=SetMonitorRequest(
                enabled=True, dest_port=24, source_ports=[1, 2]
            ),
        )
    raw = route.calls.last.request.url.raw_path.decode()
    assert "portCopySourceMask=c0+00+00+00" in raw


def test_monitor_source_mask_matches_applet_examples() -> None:
    # Bit positions per MonitorList.java:36 — 1 << (32 - n), n = port index
    # within its 32-port word.
    assert monitor_source_mask([1]) == "80 00 00 00"
    assert monitor_source_mask([1, 2]) == "c0 00 00 00"
    assert monitor_source_mask([24]) == "00 00 01 00"
    assert monitor_source_mask([32]) == "00 00 00 01"
    assert monitor_source_mask(list(range(1, 25))) == "ff ff ff 00"
    # Order must not matter.
    assert monitor_source_mask([2, 1]) == monitor_source_mask([1, 2])


def test_monitor_source_mask_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(ValueError):
        monitor_source_mask([])
    with pytest.raises(ValueError):
        monitor_source_mask([0])
    with pytest.raises(ValueError):
        monitor_source_mask([33])


def test_set_monitor_enable_requires_dest_and_ports() -> None:
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True)
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True, dest_port=24)
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True, source_ports=[1])
    # Empty source set is as invalid as a missing one.
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True, dest_port=24, source_ports=[])
    # Out-of-range ports must be rejected before they reach the wire.
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True, dest_port=24, source_ports=[0])
    with pytest.raises(ValueError):
        SetMonitorRequest(enabled=True, dest_port=33, source_ports=[1])


@respx.mock
async def test_set_monitor_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_monitor(t, request=SetMonitorRequest(enabled=False))
