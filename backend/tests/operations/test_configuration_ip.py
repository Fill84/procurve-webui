"""Tests for Configuration → IP operations.

- get_ip_page:         scrape ip1.html + ip2.html
- set_ip_config:       /cgi/ip?rt=...&VLAN=...&mode=...&apply=...
- set_default_gateway: /cgi/gateway?rt=...
"""
from ipaddress import IPv4Address
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import (
    IpMode,
    SetDefaultGatewayRequest,
    SetIpConfigRequest,
)
from procurve_client.operations.configuration import (
    get_ip_page,
    set_default_gateway,
    set_ip_config,
)
from procurve_client.transport import ProcurveTransport


def _load_mirror(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "research" / "mirror" / "2026-04-23" / "configuration" / name
    return path.read_text(encoding="utf-8")


@respx.mock
async def test_get_ip_page_parses_both_frames() -> None:
    respx.get("http://192.0.2.3/configuration/ip2.html").mock(
        return_value=Response(200, text=_load_mirror("ip2.html"))
    )
    respx.get("http://192.0.2.3/configuration/ip1.html").mock(
        return_value=Response(200, text=_load_mirror("ip1.html"))
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_ip_page(t)
    assert page.vlan_id == 97
    assert page.mode is IpMode.DHCP
    # Fixture was captured from the live switch at 192.168.178.3 — the HTML
    # response has that value baked in, so the assertion matches the bytes.
    assert page.ip_address == IPv4Address("192.168.178.3")
    assert page.subnet_mask == "255.255.255.0"
    assert page.gateway == IPv4Address("192.168.178.1")


@respx.mock
async def test_get_ip_page_missing_vlan_hidden_raises() -> None:
    respx.get("http://192.0.2.3/configuration/ip2.html").mock(
        return_value=Response(200, text="<html>nope</html>")
    )
    respx.get("http://192.0.2.3/configuration/ip1.html").mock(
        return_value=Response(200, text=_load_mirror("ip1.html"))
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_ip_page(t)


@respx.mock
async def test_set_ip_config_emits_expected_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/ip").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_ip_config(
            t,
            request=SetIpConfigRequest(
                gateway=IPv4Address("192.168.178.1"),
                vlan_id=97,
                mode=IpMode.MANUAL,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["rt"] == "192.168.178.1"
    assert q["VLAN"] == "97"
    assert q["mode"] == "2"
    assert q["apply"] == " Apply Changes "


@respx.mock
async def test_set_ip_config_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_ip_config(
                t,
                request=SetIpConfigRequest(
                    gateway=IPv4Address("0.0.0.0"),  # noqa: S104 — "clear gateway" sentinel
                    vlan_id=1,
                    mode=IpMode.DHCP,
                ),
            )


@respx.mock
async def test_set_default_gateway_emits_rt_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/gateway").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_default_gateway(
            t,
            request=SetDefaultGatewayRequest(gateway=IPv4Address("10.0.0.1")),
        )
    q = route.calls.last.request.url.params
    assert q["rt"] == "10.0.0.1"
    assert "apply" not in q  # No submit button on this form.


@respx.mock
async def test_set_default_gateway_clear_with_zero_addr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/gateway").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_default_gateway(
            t,
            request=SetDefaultGatewayRequest(
                gateway=IPv4Address("0.0.0.0"),  # noqa: S104 — clears the gateway
            ),
        )
    assert route.calls.last.request.url.params["rt"] == "0.0.0.0"  # noqa: S104


def test_set_ip_config_request_validates_vlan_range() -> None:
    with pytest.raises(ValueError):
        SetIpConfigRequest(
            gateway=IPv4Address("1.1.1.1"), vlan_id=0, mode=IpMode.MANUAL
        )
    with pytest.raises(ValueError):
        SetIpConfigRequest(
            gateway=IPv4Address("1.1.1.1"), vlan_id=5000, mode=IpMode.MANUAL
        )
