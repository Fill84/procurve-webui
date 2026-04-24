"""Unit tests for ProcurveTransport."""
import pytest
import respx
from httpx import Response

from procurve_client.auth import BasicAuth, NoneAuth
from procurve_client.errors import AuthError, TransportError
from procurve_client.transport import ProcurveTransport


def test_transport_defaults():
    t = ProcurveTransport(host="192.0.2.3")
    assert t.host == "192.0.2.3"
    assert t.port == 80
    assert t.base_url == "http://192.0.2.3"
    assert isinstance(t.auth, NoneAuth)


def test_transport_explicit_auth_and_port():
    t = ProcurveTransport(
        host="switch.lan",
        port=8080,
        auth=BasicAuth(username="admin", password="pw"),  # noqa: S106
    )
    assert t.port == 8080
    assert t.base_url == "http://switch.lan:8080"
    assert isinstance(t.auth, BasicAuth)


async def test_transport_is_async_context_manager():
    async with ProcurveTransport(host="192.0.2.3") as t:
        assert t._client is not None
    # after __aexit__ the client is closed
    assert t._client is None


@respx.mock
async def test_get_returns_response_on_2xx():
    respx.get("http://192.0.2.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        r = await t.get("/home.html")
    assert r.status_code == 200
    assert "<html>" in r.text


@respx.mock
async def test_get_raises_transport_error_on_network_issue():
    respx.get("http://192.0.2.3/home.html").mock(side_effect=ConnectionError("boom"))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(TransportError):
            await t.get("/home.html")


@respx.mock
async def test_get_raises_auth_error_on_401():
    respx.get("http://192.0.2.3/home.html").mock(return_value=Response(401, text=""))
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(AuthError):
            await t.get("/home.html")


@respx.mock
async def test_get_attaches_auth_headers_when_basic():
    route = respx.get("http://192.0.2.3/home.html").mock(return_value=Response(200, text="x"))
    async with ProcurveTransport(
        host="192.0.2.3",
        auth=BasicAuth(username="admin", password="pw"),  # noqa: S106
    ) as t:
        await t.get("/home.html")
    assert route.called
    assert route.calls.last.request.headers["Authorization"].startswith("Basic ")
