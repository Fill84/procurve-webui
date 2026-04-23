"""Unit tests for Identity-tab operations."""
from ipaddress import IPv4Address
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import ParseError
from procurve_client.operations.identity import read_identity_page
from procurve_client.transport import ProcurveTransport


@pytest.fixture
def identity_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "read_identity_page.response.txt").read_text(encoding="ascii")


@respx.mock
async def test_read_identity_page_parses_fixture(identity_html: str) -> None:
    respx.get("http://192.168.178.3/identity/identity.html").mock(
        return_value=Response(200, text=identity_html, headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        identity = await read_identity_page(t)

    assert identity.system_name == "HP2810_01"
    assert identity.system_location == "Kamer"
    assert identity.system_contact == "Phillippe Pelzer"
    assert identity.uptime_centiseconds == 3800860
    assert identity.cpu_pct == 1
    assert identity.memory_total_bytes == 23821200
    assert identity.memory_free_bytes == 15123584
    assert "ProCurve Switch 2810-24G" in identity.product
    assert "J9021A" in identity.product
    assert identity.base_mac == "00:1D:B3:B7:0E:00"
    assert identity.serial_number == "CN814XI06X"
    assert "N.11.78" in identity.firmware_version
    assert "ROM N.10.01" in identity.firmware_version
    assert identity.ip_address == IPv4Address("192.168.178.3")
    assert identity.management_server_url == "https://www.hpe.com/networking/support"


@respx.mock
async def test_read_identity_page_missing_marker_raises() -> None:
    respx.get("http://192.168.178.3/identity/identity.html").mock(
        return_value=Response(200, text="<html>not the identity page</html>",
                              headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ParseError):
            await read_identity_page(t)


@respx.mock
async def test_read_identity_page_maps_empty_url_to_none() -> None:
    """When link("") is emitted, the switch renders '(None)' — map to None."""
    synthetic = """
<html><body>
<tr><th>System Name:</th><td>sw1</td></tr>
<tr><th>System Location:</th><td>rack</td></tr>
<tr><th>System Contact:</th><td>ops</td></tr>
<tr><th>System Up-Time:</th><td>""" + 'ft("123")' + """</td></tr>
<tr><th>System CPU Util(%):</th><td>3</td></tr>
<tr><th>System Memory:</th><td>Total - 10 Free - 5</td></tr>
<tr><th>Product:</th><td>Test (X)</td></tr>
<tr><th>Base MAC Address:</th><td>aa bb cc dd ee ff</td></tr>
<tr><th>Serial Number:</th><td>SN1</td></tr>
<tr><th>Version:</th><td>N.0, ROM N.0</td></tr>
<tr><th>IP Address:</th><td>10.0.0.1</td></tr>
<tr><th>Management Server:</th><td>""" + 'link("")' + """</td></tr>
</body></html>"""
    respx.get("http://192.168.178.3/identity/identity.html").mock(
        return_value=Response(200, text=synthetic, headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        identity = await read_identity_page(t)
    assert identity.management_server_url is None
    assert identity.ip_address == IPv4Address("10.0.0.1")
    assert identity.base_mac == "AA:BB:CC:DD:EE:FF"
