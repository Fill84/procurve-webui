"""Tests for Configuration → Ports operations.

- get_portscfg:    /cgi/get_portscfg (10-field tilde rows)
- get_port_form:   /cgi/port_form?indeces=... (HTML form scrape)
- set_port_config: /cgi/mod_ports?indeces=...&_portName=...&...
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.port import (
    PortMode,
    SetPortConfigRequest,
)
from procurve_client.operations.configuration import (
    get_port_form,
    get_portscfg,
    set_port_config,
)
from procurve_client.transport import ProcurveTransport


def _read_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="ascii")


# ---- get_portscfg --------------------------------------------------------

@respx.mock
async def test_get_portscfg_parses_all_24_ports(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_portscfg.response.txt")
    respx.get("http://192.0.2.3/cgi/get_portscfg").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        ports = await get_portscfg(t)
    assert len(ports.ports) == 24
    p1 = ports.ports[0]
    assert p1.port == 1
    assert p1.port_name == "1-Dyn1"
    assert p1.port_type_label == " "
    assert p1.port_type == "100/1000T"
    assert p1.enabled is True
    assert p1.config_status == "."
    assert p1.config_mode == "Auto-1000"
    assert p1.flow_control is True
    assert p1.extra == 0
    # Port 18 has UPS label and Auto mode.
    p18 = ports.ports[17]
    assert p18.port_type_label == "UPS"
    assert p18.config_mode == "Auto"
    # Port 23 is administratively disabled.
    p23 = ports.ports[22]
    assert p23.enabled is False


@respx.mock
async def test_get_portscfg_short_row_raises() -> None:
    respx.get("http://192.0.2.3/cgi/get_portscfg").mock(
        return_value=Response(200, text="1~name~ ~type~Yes~.\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_portscfg(t)


@respx.mock
async def test_get_portscfg_rejects_bad_enabled() -> None:
    body = "1~n~ ~100/1000T~Maybe~.~Auto~ ~Enable~0\n"
    respx.get("http://192.0.2.3/cgi/get_portscfg").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_portscfg(t)


@respx.mock
async def test_get_portscfg_rejects_bad_flow_control() -> None:
    body = "1~n~ ~100/1000T~Yes~.~Auto~ ~Foo~0\n"
    respx.get("http://192.0.2.3/cgi/get_portscfg").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_portscfg(t)


# ---- get_port_form -------------------------------------------------------

@respx.mock
async def test_get_port_form_parses_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_port_form.response.txt")
    route = respx.get("http://192.0.2.3/cgi/port_form").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        form = await get_port_form(t, ports=[1])
    assert route.calls.last.request.url.params["indeces"] == "1"
    assert form.ports == [1]
    assert form.port_name == ""
    assert form.admin_enabled is True
    assert form.mode is PortMode.AUTO_1000
    assert form.flow_control_enabled is True


@respx.mock
async def test_get_port_form_multi_port_indeces_csv(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_port_form.response.txt")
    route = respx.get("http://192.0.2.3/cgi/port_form").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await get_port_form(t, ports=[1, 2, 3])
    assert route.calls.last.request.url.params["indeces"] == "1,2,3"


async def test_get_port_form_rejects_empty_ports() -> None:
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ValueError):
            await get_port_form(t, ports=[])


@respx.mock
async def test_get_port_form_missing_admin_raises() -> None:
    body = "<html><Input Type='hidden' Name='indeces' Value='1'></html>"
    respx.get("http://192.0.2.3/cgi/port_form").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_port_form(t, ports=[1])


# ---- set_port_config -----------------------------------------------------

@respx.mock
async def test_set_port_config_emits_expected_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/mod_ports").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_port_config(
            t,
            request=SetPortConfigRequest(
                ports=[1, 2],
                name="uplink",
                admin_enabled=True,
                mode=PortMode.AUTO_1000,
                flow_control_enabled=True,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1,2"
    assert q["_portName"] == "uplink"
    assert q["hpSwitchPortAdminStatus"] == "1"
    assert q["hpSwitchPortFastEtherMode"] == "9"
    assert q["hpSwitchPortFlowControl"] == "2"
    assert q["apply"] == " Apply Settings "
    # ListPane.submitMultipleItems URL-encodes the separator between items
    # (URLEncoder.encode(","), ListPane.java:572) — unlike set_bobports,
    # whose SwitchBob path appends the comma raw. Byte-level check:
    raw = route.calls.last.request.url.raw_path.decode()
    assert "indeces=1%2C2" in raw
    assert "apply=+Apply+Settings+" in raw


@respx.mock
async def test_set_port_config_disable_flow_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/mod_ports").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_port_config(
            t,
            request=SetPortConfigRequest(
                ports=[24],
                name="",
                admin_enabled=False,
                mode=PortMode.AUTO,
                flow_control_enabled=False,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["hpSwitchPortAdminStatus"] == "2"
    assert q["hpSwitchPortFlowControl"] == "1"
    assert q["_portName"] == ""


@respx.mock
async def test_set_port_config_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_port_config(
                t, request=SetPortConfigRequest(ports=[1])
            )


def test_set_port_config_rejects_tilde_in_name() -> None:
    with pytest.raises(ValueError):
        SetPortConfigRequest(ports=[1], name="bad~name")


def test_set_port_config_rejects_overlong_name() -> None:
    with pytest.raises(ValueError):
        SetPortConfigRequest(ports=[1], name="x" * 65)


def test_set_port_config_rejects_flow_on_half_duplex() -> None:
    with pytest.raises(ValueError):
        SetPortConfigRequest(
            ports=[1], mode=PortMode.HDX_100, flow_control_enabled=True
        )


def test_set_port_config_rejects_empty_ports() -> None:
    with pytest.raises(ValueError):
        SetPortConfigRequest(ports=[])


def test_port_mode_has_no_value_6() -> None:
    # Value 6 is deliberately absent — legacy mode removed in this firmware.
    assert 6 not in {m.value for m in PortMode}
