"""Tests for Configuration → Support operations.

- get_support_page: scrape support.html for the two URL fields
- set_support:      /cgi/support?_SuppURL=...&hpHttpMgMgmtSrvrURL=...
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError, WriteDisabledError
from procurve_client.models.network import SetSupportRequest
from procurve_client.operations.configuration import (
    get_support_page,
    set_support,
)
from procurve_client.transport import ProcurveTransport


def _load_mirror(name: str) -> str:
    root = Path(__file__).resolve().parents[3]
    path = root / "research" / "mirror" / "2026-04-23" / "configuration" / name
    return path.read_text(encoding="utf-8")


@respx.mock
async def test_get_support_page_parses_mirror() -> None:
    respx.get("http://192.0.2.3/configuration/support.html").mock(
        return_value=Response(200, text=_load_mirror("support.html"))
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        page = await get_support_page(t)
    assert page.support_url == "http://www.procurve.com"
    assert page.mgmt_url == "https://www.hpe.com/networking/support"


@respx.mock
async def test_get_support_page_missing_fields_raises() -> None:
    respx.get("http://192.0.2.3/configuration/support.html").mock(
        return_value=Response(200, text="<html>empty</html>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ParseError):
            await get_support_page(t)


@respx.mock
async def test_set_support_emits_underscore_and_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.get("http://192.0.2.3/cgi/support").mock(
        return_value=Response(200, text="OK~")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await set_support(
            t,
            request=SetSupportRequest(
                support_url="http://example.com/support",
                mgmt_url="http://example.com/mgmt",
            ),
        )
    q = route.calls.last.request.url.params
    # Underscore prefix on _SuppURL is preserved verbatim.
    assert q["_SuppURL"] == "http://example.com/support"
    assert q["hpHttpMgMgmtSrvrURL"] == "http://example.com/mgmt"
    assert q["indeces"] == "0"
    assert q["apply"] == " Apply Changes "


@respx.mock
async def test_set_support_blocked_by_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("READ_ONLY", "true")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await set_support(
                t,
                request=SetSupportRequest(
                    support_url="x", mgmt_url="y"
                ),
            )


def test_set_support_rejects_empty_url() -> None:
    # SUPPORT_FIELD_PATTERN requires at least one char (`+`).
    with pytest.raises(ValueError):
        SetSupportRequest(support_url="", mgmt_url="x")


def test_set_support_rejects_tilde() -> None:
    with pytest.raises(ValueError):
        SetSupportRequest(support_url="bad~url", mgmt_url="ok")


def test_set_support_rejects_overlong_url() -> None:
    with pytest.raises(ValueError):
        SetSupportRequest(support_url="x" * 104, mgmt_url="ok")
