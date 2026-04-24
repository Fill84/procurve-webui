"""Unit tests for upload_config (exemplar write).

No live switch POSTs. Verifies:
  1. The write is blocked when READ_ONLY=true.
  2. The request shape matches the contract documented in
     research/protocol/backup/upload_config.md.
  3. The file-part body is byte-identical to the source backup.
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import WriteDisabledError
from procurve_client.models.backup import ConfigBackup
from procurve_client.operations.backup import (
    UPLOAD_CONFIGFILE_FIELD,
    UPLOAD_CONFIGNAME_FIELD,
    UPLOAD_PATH,
    UPLOAD_REBOOT_FIELD,
    UPLOAD_SUBMIT_FIELD,
    upload_config,
)
from procurve_client.transport import ProcurveTransport


def _reference_backup() -> ConfigBackup:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    return ConfigBackup.from_bytes(fixture.read_bytes())


def test_upload_constants_match_phase0_contract():
    # Guard against accidental renames. Contract is locked.
    assert UPLOAD_PATH == "/cgi/upload"
    assert UPLOAD_CONFIGNAME_FIELD == "configname"
    assert UPLOAD_CONFIGFILE_FIELD == "configfile"
    assert UPLOAD_REBOOT_FIELD == "reboot"
    assert UPLOAD_SUBMIT_FIELD == "Uplo"


async def test_upload_config_blocked_when_read_only(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "true")
    backup = _reference_backup()
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(WriteDisabledError):
            await upload_config(t, backup=backup)


@respx.mock
async def test_upload_config_posts_multipart(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await upload_config(t, backup=backup)
    assert route.called
    req = route.calls.last.request
    ctype = req.headers["Content-Type"]
    assert ctype.startswith("multipart/form-data")
    body = req.content
    # Contract fields present
    assert b'name="configname"' in body
    assert b'name="configfile"' in body
    assert b'filename="CONFIG.pcc"' in body
    assert b'name="Uplo"' in body
    # Tight byte-exact match for the Uplo submit-field serialization.
    # `b"Upload" in body` alone is too loose because "Upload" also
    # appears in other parts of a multipart body.
    assert b'Content-Disposition: form-data; name="Uplo"\r\n\r\nUpload\r\n' in body
    # Default: reboot checkbox omitted
    assert b'name="reboot"' not in body


@respx.mock
async def test_upload_config_includes_reboot_when_requested(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await upload_config(t, backup=backup, reboot_after=True)
    body = route.calls.last.request.content
    assert b'name="reboot"' in body
    assert b"on" in body


@respx.mock
async def test_upload_config_strips_cr_before_upload(monkeypatch):
    """File part body must have no \\r (only \\n) so switch storage round-trips byte-identically.

    See research/backups/2026-04-23/README.md for the background — the switch's
    /cgi/upload endpoint adds its own \\r to every \\n, so uploading already-CRLF
    text results in doubled-CR storage.
    """
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.0.2.3") as t:
        await upload_config(t, backup=backup)
    body = route.calls.last.request.content

    # Extract the file part
    marker = b'filename="CONFIG.pcc"'
    idx = body.find(marker)
    assert idx >= 0
    headers_end = body.find(b"\r\n\r\n", idx)
    assert headers_end >= 0
    content_start = headers_end + 4
    boundary_marker = b"\r\n--"
    content_end = body.find(boundary_marker, content_start)
    file_bytes = body[content_start:content_end]

    # File part must contain \n but never \r (CRs are inserted by switch storage)
    assert b"\r" not in file_bytes
    assert b"\n" in file_bytes

    # Content is the baseline with all \r\n normalized to \n
    expected = backup.data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    assert file_bytes == expected


async def test_upload_config_custom_configname(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    with respx.mock:
        route = respx.post("http://192.0.2.3/cgi/upload").mock(
            return_value=Response(200, text="OK")
        )
        async with ProcurveTransport(host="192.0.2.3") as t:
            await upload_config(t, backup=backup, configname="MyBackup")
        body = route.calls.last.request.content
        assert b"MyBackup" in body
