"""Tests for Configuration → VLAN subsystem (15 operations).

Fixtures live under `research/fixtures/vlan__*.response.txt`. Writes are
never exercised against a live switch; responses are synthesised from the
protocol-doc sketches (add/del/ren/setPrimary) or treated as a bare `OK`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import OperationError, ParseError, WriteDisabledError
from procurve_client.models.vlan import (
    AddVlanRequest,
    DelVlanRequest,
    GvrpPortMode,
    PortModeChange,
    RenVlanRequest,
    SetGvrpModeRequest,
    SetGvrpPortsRequest,
    SetPrimaryVlanRequest,
    SetVlanModeRequest,
    SetVlanPortsRequest,
    VlanPortMode,
)
from procurve_client.operations.vlan import (
    add_vlan,
    delete_vlans,
    get_gvrp_mode,
    get_gvrp_ports,
    get_vlan_mode,
    get_vlan_ports,
    get_vlan_protocol,
    get_vlans_all,
    list_vlans,
    rename_vlan,
    set_gvrp_mode,
    set_gvrp_ports,
    set_primary_vlan,
    set_vlan_mode,
    set_vlan_ports,
)
from procurve_client.transport import ProcurveTransport

HOST = "http://192.0.2.3"


def _fixture(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "research" / "fixtures" / name).read_text(encoding="utf-8")


# =====================================================================
# Read fixtures
# =====================================================================


@respx.mock
async def test_get_vlans_all_parses_live_fixture() -> None:
    body = _fixture("vlan__getVLANAll.response.txt")
    respx.get(f"{HOST}/cgi/getVLANAll").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlans_all(t)
    assert len(res.vlans) == 1
    v = res.vlans[0]
    assert v.vlan_id == 1
    assert v.vlan_name == "DEFAULT_VLAN (Primary)"
    assert v.vlan_type == "STATIC"
    assert v.tagged_ports == "None"
    assert v.gvrp_ports == "None"
    assert v.untagged_ports == "7-8,11-14,17-24, Dyn1-Dyn3"
    assert v.forbid_ports == "None"
    assert v.auto_ports == "None"


@respx.mock
async def test_get_vlans_all_rejects_short_row() -> None:
    respx.get(f"{HOST}/cgi/getVLANAll").mock(
        return_value=Response(200, text="1~DEFAULT~STATIC~None\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_vlans_all(t)


@respx.mock
async def test_get_vlans_all_rejects_empty_body() -> None:
    respx.get(f"{HOST}/cgi/getVLANAll").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_vlans_all(t)


@respx.mock
async def test_list_vlans_parses_live_fixture() -> None:
    body = _fixture("vlan__listVLANS.response.txt")
    respx.get(f"{HOST}/cgi/listVLANS").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await list_vlans(t)
    assert [(v.vlan_id, v.vlan_name) for v in res.vlans] == [
        (1, "DEFAULT_VLAN (Primary)"),
    ]


@respx.mock
async def test_list_vlans_parses_multiple_pairs() -> None:
    respx.get(f"{HOST}/cgi/listVLANS").mock(
        return_value=Response(200, text="1~DEFAULT_VLAN (Primary)~10~Guests~20~Servers~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await list_vlans(t)
    assert [(v.vlan_id, v.vlan_name) for v in res.vlans] == [
        (1, "DEFAULT_VLAN (Primary)"),
        (10, "Guests"),
        (20, "Servers"),
    ]


@respx.mock
async def test_get_vlan_mode_on_fixture() -> None:
    body = _fixture("vlan__getVLANMode.response.txt")
    respx.get(f"{HOST}/cgi/getVLANMode").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlan_mode(t)
    assert res.enabled is True


@respx.mock
async def test_get_vlan_mode_off_synthetic() -> None:
    respx.get(f"{HOST}/cgi/getVLANMode").mock(return_value=Response(200, text="OFF\n"))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlan_mode(t)
    assert res.enabled is False


@respx.mock
async def test_get_vlan_mode_empty_body_raises() -> None:
    respx.get(f"{HOST}/cgi/getVLANMode").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_vlan_mode(t)


@respx.mock
async def test_get_gvrp_mode_off_fixture() -> None:
    body = _fixture("vlan__getGVRPMode.response.txt")
    respx.get(f"{HOST}/cgi/getGVRPMode").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_gvrp_mode(t)
    assert res.enabled is False


@respx.mock
async def test_get_gvrp_ports_fixture_marks_garbage_as_none() -> None:
    """Fixture has GVRP=OFF, so ports 1-6 carry uninitialised int garbage."""
    body = _fixture("vlan__getGVRPPort.response.txt")
    respx.get(f"{HOST}/cgi/getGVRPPort").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_gvrp_ports(t)
    assert res.gvrp_enable is False
    by_name = {p.port_name: p for p in res.ports}
    # Garbage mode values are normalised to None.
    for name in ("1", "2", "3", "4", "5", "6"):
        assert by_name[name].mode is None, f"port {name} should be None"
    # Valid mode codes pass through as the IntEnum.
    assert by_name["7"].mode == GvrpPortMode.LEARN
    assert by_name["9"].mode == GvrpPortMode.BLOCK
    assert by_name["10"].mode == GvrpPortMode.DISABLE
    assert by_name["Dyn3"].mode == GvrpPortMode.LEARN
    assert by_name["Dyn3"].port_id == 75


@respx.mock
async def test_get_gvrp_ports_on_sentinel_is_true() -> None:
    respx.get(f"{HOST}/cgi/getGVRPPort").mock(
        return_value=Response(200, text="ON~1~1~0~2~2~1~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_gvrp_ports(t)
    assert res.gvrp_enable is True
    assert [p.mode for p in res.ports] == [
        GvrpPortMode.DISABLE,
        GvrpPortMode.LEARN,
    ]


@respx.mock
async def test_get_vlan_ports_live_fixture() -> None:
    body = _fixture("vlan__getVLANPort.response.txt")
    route = respx.get(f"{HOST}/cgi/getVLANPort").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlan_ports(t, vlan_id=1)
    assert route.calls.last.request.url.params["VLAN_ID"] == "1"
    assert res.vlan_id == 1
    assert res.gvrp_enable is False
    by_name = {p.port_name: p for p in res.ports}
    assert by_name["7"].mode == VlanPortMode.UNTAGGED
    assert by_name["9"].mode == VlanPortMode.AUTO
    assert by_name["11"].mode == VlanPortMode.UNTAGGED
    assert by_name["Dyn1"].mode == VlanPortMode.UNTAGGED
    # Total rows: 24 fixed + 3 Dyn = 27.
    assert len(res.ports) == 27


@respx.mock
async def test_get_vlan_ports_rejects_invalid_mode() -> None:
    respx.get(f"{HOST}/cgi/getVLANPort").mock(
        return_value=Response(200, text="OFF~1~1~7~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_vlan_ports(t, vlan_id=1)


async def test_get_vlan_ports_rejects_out_of_range_vlan_id_before_transport() -> None:
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ValueError):
            await get_vlan_ports(t, vlan_id=5000)


@respx.mock
async def test_get_vlan_protocol_empty_body_is_ok() -> None:
    respx.get(f"{HOST}/cgi/getVLANProtocol").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlan_protocol(t, vlan_id=1)
    assert res.vlan_id == 1
    assert res.protocols == []


@respx.mock
async def test_get_vlan_protocol_parses_list() -> None:
    respx.get(f"{HOST}/cgi/getVLANProtocol").mock(
        return_value=Response(200, text="IP~IPX~AppleTalk~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_vlan_protocol(t, vlan_id=2)
    assert res.protocols == ["IP", "IPX", "AppleTalk"]


# =====================================================================
# Write request models: validation
# =====================================================================


def test_add_vlan_request_rejects_tilde_in_name() -> None:
    with pytest.raises(ValueError):
        AddVlanRequest(vlan_id=5, vlan_name="bad~name")


def test_add_vlan_request_rejects_space_in_name() -> None:
    with pytest.raises(ValueError):
        AddVlanRequest(vlan_id=5, vlan_name="has space")


def test_add_vlan_request_rejects_overlong_name() -> None:
    with pytest.raises(ValueError):
        AddVlanRequest(vlan_id=5, vlan_name="x" * 13)


def test_add_vlan_request_rejects_out_of_range_id() -> None:
    with pytest.raises(ValueError):
        AddVlanRequest(vlan_id=5000, vlan_name="ok")


def test_del_vlan_request_requires_non_empty() -> None:
    with pytest.raises(ValueError):
        DelVlanRequest(vlan_ids=[])


def test_del_vlan_request_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        DelVlanRequest(vlan_ids=[1, 9999])


def test_ren_vlan_request_rejects_tilde() -> None:
    with pytest.raises(ValueError):
        RenVlanRequest(vlan_id=10, vlan_name="no~way")


def test_set_vlan_ports_request_rejects_bad_mode() -> None:
    with pytest.raises(ValueError):
        SetVlanPortsRequest(
            vlan_id=1,
            changes=[PortModeChange(port_id=1, mode=5)],
        )


def test_set_gvrp_ports_request_rejects_mode_3() -> None:
    # GVRP only accepts 0..2; VLAN port accepts 0..3.
    with pytest.raises(ValueError):
        SetGvrpPortsRequest(changes=[PortModeChange(port_id=1, mode=3)])


# =====================================================================
# Writes: wire shapes
# =====================================================================


@respx.mock
async def test_add_vlan_wire_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/addVLAN").mock(
        return_value=Response(200, text="OK~1~DEFAULT_VLAN (Primary)~20~Guest~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await add_vlan(t, request=AddVlanRequest(vlan_id=20, vlan_name="Guest"))
    q = route.calls.last.request.url.params
    assert q["VLAN_ID"] == "20"
    assert q["VLAN_NAME"] == "Guest"
    assert res.ok is True
    assert [(v.vlan_id, v.vlan_name) for v in res.vlans] == [
        (1, "DEFAULT_VLAN (Primary)"),
        (20, "Guest"),
    ]


@respx.mock
async def test_add_vlan_error_response_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/addVLAN").mock(
        return_value=Response(
            200,
            text="VLAN with this ID already exists~1~DEFAULT_VLAN (Primary)~\n",
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError) as exc:
            await add_vlan(t, request=AddVlanRequest(vlan_id=1, vlan_name="Dup"))
    assert "already exists" in str(exc.value)


@respx.mock
async def test_add_vlan_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await add_vlan(t, request=AddVlanRequest(vlan_id=20, vlan_name="Guest"))


@respx.mock
async def test_delete_vlans_preserves_duplicate_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/delVLAN").mock(return_value=Response(200, text="OK~"))
    async with ProcurveTransport(host="192.0.2.3") as t:
        await delete_vlans(t, request=DelVlanRequest(vlan_ids=[5, 6, 7]))
    url = str(route.calls.last.request.url)
    # httpx serialises list-valued dict entries as repeating query keys.
    assert url.count("VLAN_ID=") == 3
    assert "VLAN_ID=5" in url
    assert "VLAN_ID=6" in url
    assert "VLAN_ID=7" in url


@respx.mock
async def test_rename_vlan_wire_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/renVLAN").mock(
        return_value=Response(200, text="OK~1~DEFAULT_VLAN (Primary)~20~Guests~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await rename_vlan(
            t, request=RenVlanRequest(vlan_id=20, vlan_name="Guests")
        )
    q = route.calls.last.request.url.params
    assert q["VLAN_ID"] == "20"
    assert q["VLAN_NAME"] == "Guests"
    assert res.ok is True


@respx.mock
async def test_set_primary_vlan_wire_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setPrimary").mock(
        return_value=Response(200, text="OK\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_primary_vlan(
            t, request=SetPrimaryVlanRequest(vlan_id=20)
        )
    assert route.calls.last.request.url.params["VLAN_ID"] == "20"
    assert res.ok is True


@respx.mock
async def test_set_vlan_ports_interleaves_port_and_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setVLANPort").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_vlan_ports(
            t,
            request=SetVlanPortsRequest(
                vlan_id=20,
                changes=[
                    PortModeChange(port_id=5, mode=1),
                    PortModeChange(port_id=6, mode=1),
                    PortModeChange(port_id=7, mode=2),
                ],
            ),
        )
    url = str(route.calls.last.request.url)
    # The byte-exact tail matches the applet's manual string concat.
    assert url.endswith(
        "VLAN_ID=20&PORT=5&MODE=1&PORT=6&MODE=1&PORT=7&MODE=2"
    )


@respx.mock
async def test_set_vlan_ports_non_ok_body_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/setVLANPort").mock(
        return_value=Response(200, text="Cannot tag primary VLAN on trunk ports")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError) as exc:
            await set_vlan_ports(
                t,
                request=SetVlanPortsRequest(
                    vlan_id=1,
                    changes=[PortModeChange(port_id=73, mode=1)],
                ),
            )
    assert "primary VLAN" in str(exc.value)


@respx.mock
async def test_set_vlan_mode_uses_1_for_enable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setVLANMode").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_vlan_mode(t, request=SetVlanModeRequest(enabled=True))
    assert route.calls.last.request.url.params["MODE"] == "1"


@respx.mock
async def test_set_vlan_mode_uses_2_for_disable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setVLANMode").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_vlan_mode(t, request=SetVlanModeRequest(enabled=False))
    assert route.calls.last.request.url.params["MODE"] == "2"


@respx.mock
async def test_set_gvrp_mode_uses_1_for_enable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setGVRPMode").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_gvrp_mode(t, request=SetGvrpModeRequest(enabled=True))
    assert route.calls.last.request.url.params["MODE"] == "1"


@respx.mock
async def test_set_gvrp_ports_interleaves_without_vlan_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/setGVRPPort").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_gvrp_ports(
            t,
            request=SetGvrpPortsRequest(
                changes=[
                    PortModeChange(port_id=5, mode=1),
                    PortModeChange(port_id=6, mode=2),
                ],
            ),
        )
    url = str(route.calls.last.request.url)
    assert url.endswith("PORT=5&MODE=1&PORT=6&MODE=2")
    assert "VLAN_ID" not in url


@respx.mock
async def test_all_write_ops_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await delete_vlans(t, request=DelVlanRequest(vlan_ids=[5]))
        with pytest.raises(WriteDisabledError):
            await rename_vlan(
                t, request=RenVlanRequest(vlan_id=5, vlan_name="X")
            )
        with pytest.raises(WriteDisabledError):
            await set_primary_vlan(
                t, request=SetPrimaryVlanRequest(vlan_id=5)
            )
        with pytest.raises(WriteDisabledError):
            await set_vlan_ports(
                t,
                request=SetVlanPortsRequest(
                    vlan_id=5,
                    changes=[PortModeChange(port_id=1, mode=1)],
                ),
            )
        with pytest.raises(WriteDisabledError):
            await set_vlan_mode(t, request=SetVlanModeRequest(enabled=True))
        with pytest.raises(WriteDisabledError):
            await set_gvrp_mode(t, request=SetGvrpModeRequest(enabled=True))
        with pytest.raises(WriteDisabledError):
            await set_gvrp_ports(
                t,
                request=SetGvrpPortsRequest(
                    changes=[PortModeChange(port_id=1, mode=1)],
                ),
            )
