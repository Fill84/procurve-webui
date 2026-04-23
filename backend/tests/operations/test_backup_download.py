"""Unit tests for download_config (exemplar read)."""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.auth import NoneAuth
from procurve_client.errors import ProtocolError
from procurve_client.models.backup import ConfigSlot
from procurve_client.operations.backup import download_config
from procurve_client.transport import ProcurveTransport


def _reference_backup_bytes() -> bytes:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "fixtures"
        / "download_config.response.txt"
    )
    return fixture.read_bytes()


@respx.mock
async def test_download_config_default_slot():
    raw = _reference_backup_bytes()
    respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(
            200,
            content=raw,
            headers={"Content-Type": 'application/octet-stream; file="CONFIG.pcc"'},
        )
    )
    async with ProcurveTransport(host="192.168.178.3", auth=NoneAuth()) as t:
        backup = await download_config(t)
    assert backup.size == 2904
    assert backup.sha256 == (
        "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11"
    )
    assert 'hostname "HP2810_01"' in backup.text


@respx.mock
async def test_download_config_sends_expected_query():
    raw = _reference_backup_bytes()
    route = respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(
            200,
            content=raw,
            headers={"Content-Type": "application/octet-stream"},
        )
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await download_config(t, slot=ConfigSlot.SECONDARY)
    assert route.called
    req = route.calls.last.request
    assert req.url.params["idx"] == "2"
    assert req.url.params["fg"] == "2"
    assert req.url.params["D1"] == "Download"


@respx.mock
async def test_download_config_raises_on_non_attachment_response():
    # Switch returned HTML (happens when D1 is omitted) — operation must notice.
    respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(
            200,
            text="<html>oops</html>",
            headers={"Content-Type": "text/html"},
        )
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(ProtocolError):
            await download_config(t)
