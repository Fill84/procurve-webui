"""Tests for Configuration → Fault Detection operations.

- get_faultdetect_page: scrapes injected `ffs=<n>;` from web_agent.html
- set_fault_detection:  /cgi/web_agent?ffs=<n>
"""
import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import (
    FaultSensitivity,
    SetFaultDetectionRequest,
)
from procurve_client.operations.configuration import (
    get_faultdetect_page,
    set_fault_detection,
)
from procurve_client.transport import ProcurveTransport

_MIRROR_PAGE_SAMPLE = """
<html><head><script>
    ffs=32;
    dps=1;
    var ffSetting = ffs ;
</script></head><body></body></html>
"""


@respx.mock
async def test_get_faultdetect_page_parses_ffs_and_dps() -> None:
    respx.get("http://192.0.2.3/configuration/web_agent.html").mock(
        return_value=Response(200, text=_MIRROR_PAGE_SAMPLE)
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_faultdetect_page(t)
    assert page.sensitivity is FaultSensitivity.HIGH
    assert page.dps == 1


@respx.mock
async def test_get_faultdetect_page_unknown_ffs_raises() -> None:
    respx.get("http://192.0.2.3/configuration/web_agent.html").mock(
        return_value=Response(200, text="ffs=999;\ndps=0;")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_faultdetect_page(t)


@respx.mock
async def test_get_faultdetect_page_missing_ffs_raises() -> None:
    respx.get("http://192.0.2.3/configuration/web_agent.html").mock(
        return_value=Response(200, text="<html>no injection here</html>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_faultdetect_page(t)


@respx.mock
async def test_set_fault_detection_emits_ffs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/web_agent").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        ack = await set_fault_detection(
            t, request=SetFaultDetectionRequest(sensitivity=FaultSensitivity.MEDIUM)
        )
    assert ack.ok is True
    assert route.calls.last.request.url.params["ffs"] == "128"


@respx.mock
async def test_set_fault_detection_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_fault_detection(
                t, request=SetFaultDetectionRequest(sensitivity=FaultSensitivity.NEVER)
            )


def test_fault_sensitivity_enum_values() -> None:
    assert FaultSensitivity.NEVER.value == 0
    assert FaultSensitivity.HIGH.value == 32
    assert FaultSensitivity.MEDIUM.value == 128
    assert FaultSensitivity.LOW.value == 224
