"""Tests for Configuration → Device View operations.

Covers get_bobports (bare-row stream) and set_bobports (query-string write).
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.port import SetBobPortsRequest
from procurve_client.operations.configuration import get_bobports, set_bobports
from procurve_client.transport import ProcurveTransport


def _read_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="ascii")


# ---- get_bobports --------------------------------------------------------

@respx.mock
async def test_get_bobports_parses_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_bobports.response.txt")
    respx.get("http://192.168.178.3/cgi/get_bobports").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        resp = await get_bobports(t)
    assert resp.device.codename == "Pilsner"
    assert resp.device.port_count == 24
    assert len(resp.ports) == 24
    # Port 1: `1~GigT~1~1~1~` — label="1", link up, enabled
    p1 = resp.ports[0]
    assert p1.port == 1
    assert p1.kind == "GigT"
    assert p1.label == "1"
    assert p1.link is True
    assert p1.enabled is True
    assert p1.mode is None
    # Port 18: `18~GigT~18(UPS)~1~1~Auto` — has a mode token
    p18 = resp.ports[17]
    assert p18.label == "18(UPS)"
    assert p18.mode == "Auto"
    # Port 11: disabled (row `11~GigT~11~2~1~` — link="2" → disabled-link)
    p11 = resp.ports[10]
    assert p11.link is False
    # Port 23: disabled (`23~GigT~23~2~2~`)
    p23 = resp.ports[22]
    assert p23.link is False
    assert p23.enabled is False


@respx.mock
async def test_get_bobports_empty_body_raises() -> None:
    respx.get("http://192.168.178.3/cgi/get_bobports").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_bobports(t)


@respx.mock
async def test_get_bobports_skips_none_placeholder() -> None:
    body = "Pilsner~2\nnone~GigT~~0~0~\n1~GigT~1~1~1~\n"
    respx.get("http://192.168.178.3/cgi/get_bobports").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        resp = await get_bobports(t)
    assert [p.port for p in resp.ports] == [1]


@respx.mock
async def test_get_bobports_short_row_raises() -> None:
    # Only 3 fields after the device line — too short for a port row.
    body = "Pilsner~1\n1~GigT~onlylabel~\n"
    respx.get("http://192.168.178.3/cgi/get_bobports").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_bobports(t)


# ---- set_bobports --------------------------------------------------------

@respx.mock
async def test_set_bobports_blocked_by_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_bobports(
                t, request=SetBobPortsRequest(enable=True, ports=[1, 2])
            )


@respx.mock
async def test_set_bobports_emits_csv_indeces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multi-port writes emit a literal-comma indeces list and ifAdminStatus=1/2."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/set_bobports").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        ack = await set_bobports(
            t, request=SetBobPortsRequest(enable=False, ports=[5, 6, 7])
        )
    assert ack.ok is True
    assert route.calls.last.request.url.params["ifAdminStatus"] == "2"
    assert route.calls.last.request.url.params["indeces"] == "5,6,7"


@respx.mock
async def test_set_bobports_single_port_no_comma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/set_bobports").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_bobports(
            t, request=SetBobPortsRequest(enable=True, ports=[24])
        )
    assert route.calls.last.request.url.params["indeces"] == "24"
    assert route.calls.last.request.url.params["ifAdminStatus"] == "1"


def test_set_bobports_request_validates_ports_nonempty() -> None:
    with pytest.raises(ValueError):
        SetBobPortsRequest(enable=True, ports=[])


def test_set_bobports_request_rejects_zero_port() -> None:
    with pytest.raises(ValueError):
        SetBobPortsRequest(enable=True, ports=[0, 1])
