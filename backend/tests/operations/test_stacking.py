"""Tests for Configuration → Stacking subsystem (10 operations).

Read fixtures live under `research/fixtures/stacking__*.response.txt`
and were captured on a **non-stacked** switch, so every populated-shape
assertion is synthetic per the protocol docs.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import OperationError, ParseError, WriteDisabledError
from procurve_client.models.stacking import (
    DeleteMembersRequest,
    SetMembersRequest,
    SetStackCfgRequest,
)
from procurve_client.operations.stacking import (
    delete_members,
    get_applet_length,
    get_candidates,
    get_cmd_name,
    get_members,
    get_memsinfo,
    get_stack_cfg,
    get_view_all,
    set_members,
    set_stack_cfg,
)
from procurve_client.transport import ProcurveTransport

HOST = "http://192.0.2.3"


def _fixture(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    return (root / "research" / "fixtures" / name).read_text(encoding="utf-8")


# =====================================================================
# get_memsinfo
# =====================================================================


@respx.mock
async def test_get_memsinfo_live_fixture_non_stacked() -> None:
    body = _fixture("stacking__get_memsinfo.response.txt")
    respx.get(f"{HOST}/cgi/get_memsinfo").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_memsinfo(t)
    assert res.member_count == 0
    # Commander-self record still present on non-stacked.
    assert len(res.members) == 1
    m0 = res.members[0]
    assert m0.member_index == 0
    assert m0.mac_address == "001db3-b70e00"
    assert m0.system_name == "HP2810_01"
    assert m0.extra == ""


@respx.mock
async def test_get_memsinfo_multiple_members_synthetic() -> None:
    # Hypothetical 2-member shape per protocol doc.
    respx.get(f"{HOST}/cgi/get_memsinfo").mock(
        return_value=Response(
            200,
            text=(
                "2~0~001db3-b70e00~Commander~"
                "~1~001db3-aa0001~Lab-SW1~"
                "~2~001db3-aa0002~Lab-SW2~\n"
            ),
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_memsinfo(t)
    assert res.member_count == 2
    assert len(res.members) == 3
    assert [m.member_index for m in res.members] == [0, 1, 2]
    assert res.members[1].system_name == "Lab-SW1"


@respx.mock
async def test_get_memsinfo_non_integer_count_raises() -> None:
    respx.get(f"{HOST}/cgi/get_memsinfo").mock(
        return_value=Response(200, text="bogus~0~\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_memsinfo(t)


@respx.mock
async def test_get_memsinfo_truncated_group_raises() -> None:
    """A stream cut off by 2+ tokens mid-group must raise (L12); a single
    missing trailing token remains the documented padded-empty case."""
    respx.get(f"{HOST}/cgi/get_memsinfo").mock(
        return_value=Response(200, text="1~1~001db3-aa0001")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError, match="truncated"):
            await get_memsinfo(t)


@respx.mock
async def test_get_memsinfo_empty_body_raises() -> None:
    respx.get(f"{HOST}/cgi/get_memsinfo").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_memsinfo(t)


# =====================================================================
# get_stack_cfg
# =====================================================================


@respx.mock
async def test_get_stack_cfg_commander_synthetic() -> None:
    respx.get(f"{HOST}/cgi/get_stack_cfg").mock(
        return_value=Response(200, text="commander~enable~60~enable~MyStack~~enable~disable\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_stack_cfg(t)
    assert res.stack_admin_state == "commander"
    assert res.disc_admin_state == "enable"
    assert res.disc_interval == 60
    assert res.stack_feature_state == "enable"
    assert res.stack_name == "MyStack"
    assert res.command_mac_addr == ""
    assert res.auto_grab_state == "enable"
    assert res.auto_join_state == "disable"


@respx.mock
async def test_get_stack_cfg_error_response_raises() -> None:
    respx.get(f"{HOST}/cgi/get_stack_cfg").mock(
        return_value=Response(200, text="error~Stacking subsystem not ready\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError) as exc:
            await get_stack_cfg(t)
    assert "Stacking subsystem not ready" in str(exc.value)


@respx.mock
async def test_get_stack_cfg_short_body_raises() -> None:
    respx.get(f"{HOST}/cgi/get_stack_cfg").mock(
        return_value=Response(200, text="commander~enable~60\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_stack_cfg(t)


# =====================================================================
# get_members
# =====================================================================


@respx.mock
async def test_get_members_live_fixture_empty() -> None:
    body = _fixture("stacking__get_members.response.txt")
    respx.get(f"{HOST}/cgi/get_members").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_members(t)
    assert res.members == []


@respx.mock
async def test_get_members_populated_synthetic() -> None:
    respx.get(f"{HOST}/cgi/get_members").mock(
        return_value=Response(
            200,
            text=(
                "1~001db3-aa0001~Lab-SW1~J9021A~Member Up\n"
                "2~001db3-aa0002~Lab-SW2~J9021A~Member Up\n"
                "3~001db3-aa0003~Lab-SW3~J9021A~Missing\n"
            ),
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_members(t)
    assert len(res.members) == 3
    assert res.members[0].switch_num == 1
    assert res.members[0].status == "Member Up"
    assert res.members[2].status == "Missing"


@respx.mock
async def test_get_members_error_response_raises() -> None:
    respx.get(f"{HOST}/cgi/get_members").mock(
        return_value=Response(200, text="error~Stacking not enabled\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError):
            await get_members(t)


# =====================================================================
# get_candidates
# =====================================================================


@respx.mock
async def test_get_candidates_live_fixture_empty() -> None:
    body = _fixture("stacking__get_candidates.response.txt")
    respx.get(f"{HOST}/cgi/get_candidates").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_candidates(t)
    assert res.candidates == []


@respx.mock
async def test_get_candidates_populated_synthetic() -> None:
    respx.get(f"{HOST}/cgi/get_candidates").mock(
        return_value=Response(
            200,
            text=(
                "001db3-cc0001~Candidate-SW1~J9021A\n"
                "001db3-cc0002~Candidate-SW2~ J9021A\n"  # leading space on device_type
            ),
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_candidates(t)
    assert len(res.candidates) == 2
    # Leading space on the second device_type should be trimmed per applet.
    assert res.candidates[1].device_type == "J9021A"


# =====================================================================
# get_view_all
# =====================================================================


@respx.mock
async def test_get_view_all_live_fixture_non_stacked() -> None:
    body = _fixture("stacking__get_view_all.response.txt")
    respx.get(f"{HOST}/cgi/get_view_all").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_view_all(t)
    assert len(res.switches) == 1
    row = res.switches[0]
    assert row.mac_addr == "001db3-b70e00"
    assert row.system_name == "HP2810_01"
    assert row.stack_status == "Stacking Disabled"
    # On non-stacked the fourth token is the literal 'Others:' header.
    assert row.stack_name == "Others:"


@respx.mock
async def test_get_view_all_populated_synthetic() -> None:
    respx.get(f"{HOST}/cgi/get_view_all").mock(
        return_value=Response(
            200,
            text=(
                "001db3-aa0001~Lab-SW1~Commander~Lab\n"
                "001db3-aa0002~Lab-SW2~Member Up~Lab\n"
            ),
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_view_all(t)
    assert len(res.switches) == 2
    assert res.switches[0].stack_name == "Lab"


# =====================================================================
# get_cmd_name (whitespace-delimited — two shapes)
# =====================================================================


@respx.mock
async def test_get_cmd_name_live_fixture_non_stacked() -> None:
    body = _fixture("stacking__get_cmd_name.response.txt")
    respx.get(f"{HOST}/cgi/get_cmd_name").mock(return_value=Response(200, text=body))
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_cmd_name(t)
    assert res.is_stacked is False
    assert res.system_name == "HP2810_01"
    assert res.mac_addr is None
    assert res.error_message == "Error in Pdu"


@respx.mock
async def test_get_cmd_name_stacked_commander_synthetic() -> None:
    # 7 whitespace tokens: name + 6 MAC segments.
    respx.get(f"{HOST}/cgi/get_cmd_name").mock(
        return_value=Response(200, text="Lab-Commander 00 1d b3 b7 0e 00\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_cmd_name(t)
    assert res.is_stacked is True
    assert res.system_name == "Lab-Commander"
    assert res.mac_addr == "001db3-b70e00"
    assert res.error_message is None


@respx.mock
async def test_get_cmd_name_empty_body_raises() -> None:
    respx.get(f"{HOST}/cgi/get_cmd_name").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_cmd_name(t)


# =====================================================================
# get_applet_length (whitespace-delimited — bare int; commander & member)
# =====================================================================


@respx.mock
async def test_get_applet_length_commander_live_fixture() -> None:
    body = _fixture("stacking__get_applet_length.response.txt")
    respx.get(f"{HOST}/cgi/get_applet_length").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_applet_length(t)
    assert res.applet_length == 150


@respx.mock
async def test_get_applet_length_member_uses_sw_prefix() -> None:
    route = respx.get(f"{HOST}/sw3/cgi/get_applet_length").mock(
        return_value=Response(200, text="200\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await get_applet_length(t, member_num=3)
    assert res.applet_length == 200
    assert "/sw3/cgi/get_applet_length" in str(route.calls.last.request.url)


async def test_get_applet_length_rejects_out_of_range_member() -> None:
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ValueError):
            await get_applet_length(t, member_num=99)


@respx.mock
async def test_get_applet_length_non_integer_raises() -> None:
    respx.get(f"{HOST}/cgi/get_applet_length").mock(
        return_value=Response(200, text="not-a-number\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_applet_length(t)


@respx.mock
async def test_get_applet_length_empty_body_raises() -> None:
    respx.get(f"{HOST}/cgi/get_applet_length").mock(return_value=Response(200, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_applet_length(t)


# =====================================================================
# Write request model validation
# =====================================================================


def test_set_members_request_rejects_mismatched_nums() -> None:
    # Same length required; we enforce in set_members call — but the
    # model itself accepts lists of any length independently.
    req = SetMembersRequest(
        mac_addrs=["001db3-aa0001", "001db3-aa0002"],
        switch_nums=[1],
    )
    assert len(req.mac_addrs) != len(req.switch_nums)


def test_set_members_request_rejects_out_of_range_num() -> None:
    with pytest.raises(ValueError):
        SetMembersRequest(
            mac_addrs=["001db3-aa0001"],
            switch_nums=[16],
        )


def test_set_members_request_rejects_reserved_chars_in_mac() -> None:
    with pytest.raises(ValueError):
        SetMembersRequest(
            mac_addrs=["bad,mac"],
            switch_nums=[1],
        )


def test_set_members_request_rejects_query_breaking_password() -> None:
    """The password travels raw in the query string (no URL-encoding, wire
    parity with the applet) — '&', '=', '#', '?', whitespace and non-ASCII
    would truncate or inject parameters (audit L10)."""
    for bad in ("p&ss", "p=ss", "p#ss", "p?ss", "p ss", "pässwörd"):
        with pytest.raises(ValueError):
            SetMembersRequest(
                mac_addrs=["001db3-aa0001"],
                switch_nums=[1],
                manager_password=bad,
            )


def test_set_members_request_accepts_safe_password() -> None:
    req = SetMembersRequest(
        mac_addrs=["001db3-aa0001"],
        switch_nums=[1],
        manager_password="l@bP4ss!_-.",  # noqa: S106 — synthetic test value
    )
    assert req.manager_password == "l@bP4ss!_-."  # noqa: S105


def test_set_stack_cfg_request_rejects_query_breaking_strings() -> None:
    """`sn` (stack name) and `ma` also ride the raw query string (L10)."""
    for field in ("sn", "ma"):
        for bad in ("a&b", "a=b", "a#b", "a b"):
            with pytest.raises(ValueError):
                SetStackCfgRequest(**{field: bad})
    # Clean values pass.
    assert SetStackCfgRequest(sn="Stack-1").sn == "Stack-1"


def test_delete_members_request_requires_non_empty() -> None:
    with pytest.raises(ValueError):
        DeleteMembersRequest(switch_nums=[])


def test_delete_members_request_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        DeleteMembersRequest(switch_nums=[20])


# =====================================================================
# set_stack_cfg (write)
# =====================================================================


@respx.mock
async def test_set_stack_cfg_emits_applet_key_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/set_stack_cfg").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        # sf before sn, js before ma — and all before ag / aj.
        res = await set_stack_cfg(
            t,
            request=SetStackCfgRequest(
                sf=1, cs=1, sn="Lab", ag=1
            ),
        )
    url = str(route.calls.last.request.url)
    assert url.endswith("?sf=1&cs=1&sn=Lab&ag=1")
    assert res.ok is True


@respx.mock
async def test_set_stack_cfg_disable_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/set_stack_cfg").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_stack_cfg(t, request=SetStackCfgRequest(sf=2))
    url = str(route.calls.last.request.url)
    assert url.endswith("?sf=2")


@respx.mock
async def test_set_stack_cfg_empty_request_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    # Route registered but should not be hit.
    route = respx.get(f"{HOST}/cgi/set_stack_cfg").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_stack_cfg(t, request=SetStackCfgRequest())
    assert res.ok is True
    assert route.call_count == 0


@respx.mock
async def test_set_stack_cfg_error_response_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/set_stack_cfg").mock(
        return_value=Response(
            200, text="error~Stacking must be enabled before creating a stack.\n"
        )
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(OperationError) as exc:
            await set_stack_cfg(t, request=SetStackCfgRequest(cs=1, sn="X"))
    assert "Stacking must be enabled" in str(exc.value)


# =====================================================================
# set_members (write) — byte-exact trailing commas, cleartext pass
# =====================================================================


@respx.mock
async def test_set_members_wire_shape_preserves_trailing_commas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/set_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_members(
            t,
            request=SetMembersRequest(
                mac_addrs=["001db3-aa0001", "001db3-aa0002"],
                switch_nums=[1, 2],
                manager_password="labpass",  # noqa: S106
            ),
        )
    url = str(route.calls.last.request.url)
    # Trailing commas on addrs AND nums; pass in cleartext; key order addrs, nums, pass.
    assert url.endswith(
        "?addrs=001db3-aa0001,001db3-aa0002,&nums=1,2,&pass=labpass"
    )
    assert res.ok is True
    assert res.errors == []


@respx.mock
async def test_set_members_empty_password_still_emits_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/set_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_members(
            t,
            request=SetMembersRequest(
                mac_addrs=["001db3-aa0001"],
                switch_nums=[1],
                manager_password="",
            ),
        )
    url = str(route.calls.last.request.url)
    assert url.endswith("?addrs=001db3-aa0001,&nums=1,&pass=")


@respx.mock
async def test_set_members_auto_rollback_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    set_route = respx.get(f"{HOST}/cgi/set_members").mock(
        return_value=Response(200, text="error~Invalid manager password\n")
    )
    del_route = respx.get(f"{HOST}/cgi/delete_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_members(
            t,
            request=SetMembersRequest(
                mac_addrs=["001db3-aa0001"],
                switch_nums=[1],
                manager_password="wrong",  # noqa: S106
            ),
        )
    assert res.ok is False
    assert len(res.errors) == 1
    assert res.errors[0].message == "Invalid manager password"
    assert res.rollback_performed is True
    assert set_route.call_count == 1
    assert del_route.call_count == 1
    # Rollback URL has the trailing comma too.
    rollback_url = str(del_route.calls.last.request.url)
    assert rollback_url.endswith("?nums=1,")


@respx.mock
async def test_set_members_rollback_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/set_members").mock(
        return_value=Response(200, text="error~Invalid manager password\n")
    )
    del_route = respx.get(f"{HOST}/cgi/delete_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await set_members(
            t,
            request=SetMembersRequest(
                mac_addrs=["001db3-aa0001"],
                switch_nums=[1],
                manager_password="wrong",  # noqa: S106
            ),
            auto_rollback=False,
        )
    assert res.ok is False
    assert res.rollback_performed is False
    assert del_route.call_count == 0


@respx.mock
async def test_set_members_rejects_length_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ValueError):
            await set_members(
                t,
                request=SetMembersRequest(
                    mac_addrs=["001db3-aa0001", "001db3-aa0002"],
                    switch_nums=[1],
                    manager_password="",
                ),
            )


# =====================================================================
# delete_members (write)
# =====================================================================


@respx.mock
async def test_delete_members_wire_shape_preserves_trailing_comma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/delete_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await delete_members(
            t,
            request=DeleteMembersRequest(switch_nums=[2, 5, 7]),
        )
    url = str(route.calls.last.request.url)
    assert url.endswith("?nums=2,5,7,")
    assert res.ok is True


@respx.mock
async def test_delete_members_single_element_still_has_trailing_comma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get(f"{HOST}/cgi/delete_members").mock(
        return_value=Response(200, text="")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await delete_members(
            t,
            request=DeleteMembersRequest(switch_nums=[3]),
        )
    assert str(route.calls.last.request.url).endswith("?nums=3,")


@respx.mock
async def test_delete_members_surfaces_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    respx.get(f"{HOST}/cgi/delete_members").mock(
        return_value=Response(200, text="error~Invalid member number 17.\n")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        res = await delete_members(
            t,
            request=DeleteMembersRequest(switch_nums=[7]),
        )
    # Defensive parse — applet never looks at the body, but we do.
    assert res.ok is False
    assert res.error_message == "Invalid member number 17."


# =====================================================================
# READ_ONLY enforcement for all 3 writes
# =====================================================================


@respx.mock
async def test_all_write_ops_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_stack_cfg(t, request=SetStackCfgRequest(sf=2))
        with pytest.raises(WriteDisabledError):
            await set_members(
                t,
                request=SetMembersRequest(
                    mac_addrs=["001db3-aa0001"],
                    switch_nums=[1],
                    manager_password="",
                ),
            )
        with pytest.raises(WriteDisabledError):
            await delete_members(
                t, request=DeleteMembersRequest(switch_nums=[1])
            )
