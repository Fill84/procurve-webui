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

from procurve_client.errors import ProtocolError, WriteDisabledError
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

# Minimal-but-valid stand-in matching the download_config contract (ASCII,
# CRLF line endings, leading ';' config-editor header). Used when the real
# gitignored reference fixture is absent (fresh clones don't have it).
_SYNTHETIC_CONFIG = (
    b"; J9021A Configuration Editor; Created on release #N.11.78\r\n"
    b"\r\n"
    b"hostname \"ProCurve Switch 2810-24G\"\r\n"
    b"snmp-server community \"public\" Unrestricted\r\n"
    b"vlan 1\r\n"
    b'   name "DEFAULT_VLAN"\r\n'
    b"   untagged 1-24\r\n"
    b"   exit\r\n"
)


def _reference_backup() -> ConfigBackup:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    if fixture.exists():
        return ConfigBackup.from_bytes(fixture.read_bytes())
    return ConfigBackup.from_bytes(_SYNTHETIC_CONFIG)


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


# ---------------------------------------------------------------------------
# Safety guards: payload sanity check + error-body detection.
# Restore is the highest-risk write in the system — a garbage payload or a
# silently-rejected upload must never be reported as success.
# ---------------------------------------------------------------------------


@respx.mock
async def test_upload_config_rejects_payload_without_config_header(monkeypatch):
    """Bytes that don't start with the ';' config header never hit the switch."""
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    bogus = ConfigBackup.from_bytes(b"definitely not a switch config\n")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ProtocolError, match="leading ';'"):
            await upload_config(t, backup=bogus)
    assert route.called is False


@respx.mock
async def test_upload_config_rejects_binary_payload(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    binary = ConfigBackup.from_bytes(b"; header then\x00binary garbage")
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ProtocolError, match="NUL"):
            await upload_config(t, backup=binary)
    assert route.called is False


@respx.mock
async def test_upload_config_force_skips_sanity_check(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="OK")
    )
    bogus = ConfigBackup.from_bytes(b"headerless but forced\n")
    async with ProcurveTransport(host="192.0.2.3") as t:
        await upload_config(t, backup=bogus, force=True)
    assert route.called


@respx.mock
async def test_upload_config_raises_on_error_page_with_200(monkeypatch):
    """The firmware returns 200 with an error page on rejects — detect it.

    research/protocol/backup/upload_config.md: success is expected to be a
    200 whose body does NOT contain 'error'.
    """
    monkeypatch.setenv("READ_ONLY", "false")
    respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(200, text="<html>ERROR: invalid config</html>")
    )
    backup = _reference_backup()
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ProtocolError, match="error marker"):
            await upload_config(t, backup=backup)


@respx.mock
async def test_upload_config_raises_on_non_200(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    respx.post("http://192.0.2.3/cgi/upload").mock(
        return_value=Response(500, text="boom")
    )
    backup = _reference_backup()
    async with ProcurveTransport(host="192.0.2.3") as t:
        with pytest.raises(ProtocolError, match="HTTP 500"):
            await upload_config(t, backup=backup)
