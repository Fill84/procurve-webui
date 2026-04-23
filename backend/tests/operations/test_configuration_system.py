"""Tests for Configuration → System operations.

- get_system_page:  scrapes name/location/contact + MAC from system.html
- set_system_info:  /cgi/system?indeces=0&sysName=...&sysLocation=...
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import SetSystemInfoRequest
from procurve_client.operations.configuration import (
    get_system_page,
    set_system_info,
)
from procurve_client.transport import ProcurveTransport


def _load_system_html() -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "research" / "mirror" / "2026-04-23" / "configuration" / "system.html"
    return path.read_text(encoding="utf-8")


@respx.mock
async def test_get_system_page_parses_mirror_html() -> None:
    body = _load_system_html()
    respx.get("http://192.168.178.3/configuration/system.html").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        page = await get_system_page(t)
    assert page.name == "HP2810_01"
    assert page.location == "Kamer"
    assert page.contact == "Phillippe Pelzer"
    assert page.mac_address == "00:1D:B3:B7:0E:00"


@respx.mock
async def test_get_system_page_missing_field_raises() -> None:
    respx.get("http://192.168.178.3/configuration/system.html").mock(
        return_value=Response(200, text="<html>no form here</html>")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_system_page(t)


@respx.mock
async def test_set_system_info_preserves_apply_button_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/system").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_system_info(
            t,
            request=SetSystemInfoRequest(
                name="TestSwitch",
                location="Lab",
                contact="me@example.com",
            ),
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "0"
    assert q["sysName"] == "TestSwitch"
    assert q["sysLocation"] == "Lab"
    assert q["sysContact"] == "me@example.com"
    # The submit button value has leading + trailing spaces by design.
    assert q["apply"] == " Apply Changes "


@respx.mock
async def test_set_system_info_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_system_info(
                t, request=SetSystemInfoRequest(name="x")
            )


def test_set_system_info_request_rejects_tilde_in_name() -> None:
    with pytest.raises(ValueError):
        SetSystemInfoRequest(name="bad~name")


def test_set_system_info_request_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        SetSystemInfoRequest(name="")


def test_set_system_info_request_rejects_overlong_name() -> None:
    with pytest.raises(ValueError):
        SetSystemInfoRequest(name="x" * 31)


def test_set_system_info_request_accepts_empty_location_contact() -> None:
    # The HTML regex is `*` (zero+) for location and contact — empty is OK.
    r = SetSystemInfoRequest(name="Valid", location="", contact="")
    assert r.location == ""
    assert r.contact == ""
