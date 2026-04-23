"""Tests for Configuration → Device Features operations.

- get_devfeatures_page: scrape features2.html for IGMP / STP state
- set_device_features:  write to one of five endpoint variants
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import SetDeviceFeaturesRequest
from procurve_client.operations.configuration import (
    get_devfeatures_page,
    set_device_features,
)
from procurve_client.transport import ProcurveTransport


def _load_mirror(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "research" / "mirror" / "2026-04-23" / "configuration" / name
    return path.read_text(encoding="utf-8")


@respx.mock
async def test_get_devfeatures_page_parses_mirror() -> None:
    respx.get("http://192.168.178.3/configuration/features2.html").mock(
        return_value=Response(200, text=_load_mirror("features2.html"))
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        page = await get_devfeatures_page(t)
    # _igmp=1 → True, _st=2 → False per the mirror.
    assert page.igmp is True
    assert page.spanning_tree is False


@respx.mock
async def test_get_devfeatures_page_invalid_oid_yields_none() -> None:
    body = "<html><script>var _igmp = Invalid OID ;\nvar _st = 1 ;</script></html>"
    respx.get("http://192.168.178.3/configuration/features2.html").mock(
        return_value=Response(200, text=body)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        page = await get_devfeatures_page(t)
    assert page.igmp is None
    assert page.spanning_tree is True


@respx.mock
async def test_get_devfeatures_page_missing_vars_raises() -> None:
    respx.get("http://192.168.178.3/configuration/features2.html").mock(
        return_value=Response(200, text="<html>no feature vars</html>")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await get_devfeatures_page(t)


@respx.mock
async def test_set_device_features_single_vlan_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/feature_set").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_device_features(
            t,
            request=SetDeviceFeaturesRequest(
                endpoint="/cgi/feature_set",
                vlan_id=1,
                igmp=True,
                spanning_tree=False,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "1"
    assert q["hpSwitchIgmpState"] == "1"
    assert q["hpSwitchStpAdminStatus"] == "2"


@respx.mock
async def test_set_device_features_global_stp_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/globalfeature_set").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_device_features(
            t,
            request=SetDeviceFeaturesRequest(
                endpoint="/cgi/globalfeature_set",
                vlan_id=1,
                spanning_tree=True,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["hpSwitchStpAdminStatus"] == "1"
    # IGMP must not appear on globalfeature_set.
    assert "hpSwitchIgmpState" not in q


@respx.mock
async def test_set_device_features_per_vlan_igmp_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.168.178.3/cgi/vlanfeature_set").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await set_device_features(
            t,
            request=SetDeviceFeaturesRequest(
                endpoint="/cgi/vlanfeature_set",
                vlan_id=10,
                igmp=False,
            ),
        )
    q = route.calls.last.request.url.params
    assert q["indeces"] == "10"
    assert q["hpSwitchIgmpState"] == "2"
    assert "hpSwitchStpAdminStatus" not in q


@respx.mock
async def test_set_device_features_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_device_features(
                t, request=SetDeviceFeaturesRequest(igmp=True)
            )
