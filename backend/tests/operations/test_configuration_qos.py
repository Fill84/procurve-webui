"""Tests for Configuration → QoS operations.

Covers:
  reads:  get_cos_appt, get_cos_userpri, get_cos_vlanpri, get_dscptable,
          get_diffserv
  writes: set_cos_appt, set_cos_userpri, set_costos_mode, set_cos_vlanpri,
          set_dscptable, set_diffserv, set_cosproto
"""
from ipaddress import IPv4Address
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.qos import (
    ApplyPolicy,
    CosTosMode,
    SetCosApptRequest,
    SetCosProtoRequest,
    SetCosTosModeRequest,
    SetCosUserPriRequest,
    SetCosVlanPriRequest,
    SetDiffservRequest,
    SetDscpTableRequest,
)
from procurve_client.operations.configuration import (
    get_cos_appt,
    get_cos_userpri,
    get_cos_vlanpri,
    get_diffserv,
    get_dscptable,
    set_cos_appt,
    set_cos_userpri,
    set_cos_vlanpri,
    set_cosproto,
    set_costos_mode,
    set_diffserv,
    set_dscptable,
)
from procurve_client.transport import ProcurveTransport


def _read_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="ascii")


# ---- get_cos_appt --------------------------------------------------------

@respx.mock
async def test_get_cos_appt_empty_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_cos_appt.response.txt")
    respx.get("http://192.168.178.3/cgi/cosapp").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await get_cos_appt(t)
    assert result.entries == []


@respx.mock
async def test_get_cos_appt_parses_synthetic_row() -> None:
    body = "http (80)~80~TCP~000000~No override\n"
    respx.get("http://192.168.178.3/cgi/cosapp").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await get_cos_appt(t)
    assert len(result.entries) == 1
    e = result.entries[0]
    assert e.application_name == "http (80)"
    assert e.port_number == 80
    assert e.type == "TCP"
    assert e.dscp == "000000"
    assert e.priority == "No override"


@respx.mock
async def test_get_cos_appt_rejects_bad_protocol() -> None:
    respx.get("http://192.168.178.3/cgi/cosapp").mock(
        return_value=Response(200, text="x~99~FOO~000000~pri\n")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_cos_appt(t)


# ---- set_cos_appt --------------------------------------------------------

@respx.mock
async def test_set_cos_appt_dscp_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosappf").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cos_appt(
            t,
            request=SetCosApptRequest(
                action="Add",
                app_id=21,
                protocol="TCP",
                policy_mode=ApplyPolicy.DSCP,
                dscp=46,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["action"] == "Add"
    assert q["app"] == "21"
    assert q["tcpudp"] == "TCP"
    assert q["ap"] == "3"
    assert q["dscp"] == "46"
    assert "src" not in q
    assert "pr" not in q


@respx.mock
async def test_set_cos_appt_user_defined_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosappf").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cos_appt(
            t,
            request=SetCosApptRequest(
                action="Add",
                app_id=0,
                protocol="TCP",
                port=5060,
                policy_mode=ApplyPolicy.P_8021,
                priority_8021p=5,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["app"] == "0"
    assert q["src"] == "5060"
    assert q["ap"] == "2"
    assert q["pr"] == "5"


def test_set_cos_appt_user_defined_requires_port() -> None:
    with pytest.raises(ValueError):
        SetCosApptRequest(
            action="Add", app_id=0, protocol="TCP", policy_mode=ApplyPolicy.NO_OVERRIDE
        )


def test_set_cos_appt_dscp_requires_dscp_value() -> None:
    with pytest.raises(ValueError):
        SetCosApptRequest(
            action="Add", app_id=1, protocol="TCP", policy_mode=ApplyPolicy.DSCP
        )


def test_set_cos_appt_p_8021_requires_priority() -> None:
    with pytest.raises(ValueError):
        SetCosApptRequest(
            action="Add", app_id=1, protocol="TCP", policy_mode=ApplyPolicy.P_8021
        )


@respx.mock
async def test_set_cos_appt_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_cos_appt(
                t,
                request=SetCosApptRequest(
                    action="Delete", app_id=1, protocol="TCP"
                ),
            )


# ---- get_cos_userpri -----------------------------------------------------

@respx.mock
async def test_get_cos_userpri_empty_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_cos_userpri.response.txt")
    respx.get("http://192.168.178.3/cgi/cosuser").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        r = await get_cos_userpri(t)
    assert r.entries == []


@respx.mock
async def test_get_cos_userpri_parses_synthetic_row() -> None:
    respx.get("http://192.168.178.3/cgi/cosuser").mock(
        return_value=Response(200, text="10.0.0.5~Disabled~0-Normal Priority\n")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        r = await get_cos_userpri(t)
    assert len(r.entries) == 1
    assert r.entries[0].ip_address == IPv4Address("10.0.0.5")
    assert r.entries[0].dscp_policy == "Disabled"
    assert r.entries[0].priority == "0-Normal Priority"


# ---- set_cos_userpri -----------------------------------------------------

@respx.mock
async def test_set_cos_userpri_dscp_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosuserf").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cos_userpri(
            t,
            request=SetCosUserPriRequest(
                action="Add",
                address=IPv4Address("10.0.0.5"),
                policy_mode=ApplyPolicy.DSCP,
                dscp=46,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["action"] == "Add"
    assert q["addr"] == "10.0.0.5"
    assert q["ap"] == "3"
    assert q["dscp"] == "46"


@respx.mock
async def test_set_cos_userpri_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosuserf").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cos_userpri(
            t,
            request=SetCosUserPriRequest(
                action="Delete",
                address=IPv4Address("10.0.0.5"),
                policy_mode=ApplyPolicy.NO_OVERRIDE,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["action"] == "Delete"
    # `dscp` / `pr` should NOT be included for NO_OVERRIDE.
    assert "dscp" not in q
    assert "pr" not in q


# ---- set_costos_mode -----------------------------------------------------

@respx.mock
async def test_set_costos_mode_diffserv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/costos").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_costos_mode(
            t, request=SetCosTosModeRequest(mode=CosTosMode.DIFFSERV)
        )
    q = route.calls.last.request.url.params
    assert q["hpSwitchCosTosConfigMode"] == "3"
    assert q["indeces"] == "0"


# ---- get_cos_vlanpri -----------------------------------------------------

@respx.mock
async def test_get_cos_vlanpri_parses_fixture(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_cos_vlanpri.response.txt")
    respx.get("http://192.168.178.3/cgi/cosvlan").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        r = await get_cos_vlanpri(t)
    assert len(r.entries) == 1
    e = r.entries[0]
    assert e.vlan_id == 1
    assert e.vlan_label == "DEFAULT_VLAN(1)"
    assert e.dscp_policy == "Disabled"
    assert e.priority == "No override"


# ---- set_cos_vlanpri -----------------------------------------------------

@respx.mock
async def test_set_cos_vlanpri_dscp_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosvlanf").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cos_vlanpri(
            t, request=SetCosVlanPriRequest(vlan_id=1, dscp=46)
        )
    q = route.calls.last.request.url.params
    assert q["dscp"] == "46"
    assert q["pr"] == "255"
    assert q["indeces"] == "1"


def test_set_cos_vlanpri_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        SetCosVlanPriRequest(vlan_id=1, dscp=46, priority_8021p=5)


def test_set_cos_vlanpri_both_defaults_ok() -> None:
    # dscp=255 + pr=255 = "clear" is allowed.
    r = SetCosVlanPriRequest(vlan_id=1)
    assert r.dscp == 255
    assert r.priority_8021p == 255


# ---- get_dscptable -------------------------------------------------------

@respx.mock
async def test_get_dscptable_parses_64_rows(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_dscptable.response.txt")
    respx.get("http://192.168.178.3/cgi/dscptable_get").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        table = await get_dscptable(t)
    assert len(table.rows) == 64
    assert table.rows[0].row_index == 1
    assert table.rows[0].codepoint == "000000"
    assert table.rows[0].dscp == 0  # derived property
    assert table.rows[63].row_index == 64
    assert table.rows[63].codepoint == "111111"
    assert table.rows[63].dscp == 63


@respx.mock
async def test_get_dscptable_short_row_raises() -> None:
    respx.get("http://192.168.178.3/cgi/dscptable_get").mock(
        return_value=Response(200, text="1~000000\n")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_dscptable(t)


# ---- set_dscptable -------------------------------------------------------

@respx.mock
async def test_set_dscptable_maps_codepoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/dscptable_set").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_dscptable(
            t,
            request=SetDscpTableRequest(row_index=47, priority_8021p=5),
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "47"
    assert q["pr"] == "5"


def test_set_dscptable_row_index_range() -> None:
    with pytest.raises(ValueError):
        SetDscpTableRequest(row_index=0, priority_8021p=1)
    with pytest.raises(ValueError):
        SetDscpTableRequest(row_index=65, priority_8021p=1)


# ---- get_diffserv --------------------------------------------------------

@respx.mock
async def test_get_diffserv_parses_64_rows(fixtures_dir: Path) -> None:
    body = _read_fixture(fixtures_dir, "get_diffserv.response.txt")
    respx.get("http://192.168.178.3/cgi/diffserv_get").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        table = await get_diffserv(t)
    assert len(table.rows) == 64
    r1 = table.rows[0]
    assert r1.row_index == 1
    assert r1.inbound_codepoint == "000000"
    assert r1.dscp_policy == "Disabled"
    assert r1.priority_label == "No override"


# ---- set_diffserv --------------------------------------------------------

@respx.mock
async def test_set_diffserv_rewrites_codepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/diffserv_set").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_diffserv(
            t, request=SetDiffservRequest(row_index=11, dscp=46)
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "11"
    assert q["dscp"] == "46"


# ---- set_cosproto --------------------------------------------------------

@respx.mock
async def test_set_cosproto_empty_form(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosproto").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cosproto(t)
    q = route.calls.last.request.url.params
    assert q["Apply"] == "Apply Changes"


@respx.mock
async def test_set_cosproto_with_explicit_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/cosproto").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_cosproto(t, request=SetCosProtoRequest())
    assert route.called
