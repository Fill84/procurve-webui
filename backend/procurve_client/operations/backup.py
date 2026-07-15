"""Backup download (read) and restore (write) operations.

Contracts from Phase 0:
- Download: GET /cgi/configfile?idx={slot}&fg={slot}&D1=Download
- Upload:   POST /cgi/upload (multipart; fields: configname, configfile, [reboot], Uplo)

See research/protocol/backup/{download_config,upload_config}.md.
"""
from __future__ import annotations

import hashlib

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ProtocolError
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.transport import ProcurveTransport

_DOWNLOAD_PATH = "/cgi/configfile"

# Upload/restore endpoint and field names from Phase 0 analysis:
# research/mirror/2026-04-23/configuration/uploadConfile.html (action, input names)
UPLOAD_PATH = "/cgi/upload"
UPLOAD_CONFIGNAME_FIELD = "configname"
UPLOAD_CONFIGFILE_FIELD = "configfile"
UPLOAD_REBOOT_FIELD = "reboot"
UPLOAD_SUBMIT_FIELD = "Uplo"  # 4-char submit button name; sic, per the HTML


@READ
async def download_config(
    transport: ProcurveTransport,
    *,
    slot: ConfigSlot = ConfigSlot.PRIMARY,
) -> ConfigBackup:
    """Download the current running-config from the switch.

    `slot` selects which config slot to read (Primary/Secondary) — the switch
    routinely stores the running-config in slot 1 (Primary). Both yield the
    same bytes on typical single-config setups.
    """
    r = await transport.get(
        _DOWNLOAD_PATH,
        params={"idx": int(slot), "fg": int(slot), "D1": "Download"},
    )
    ctype = r.headers.get("Content-Type", "")
    if "application/octet-stream" not in ctype:
        raise ProtocolError(
            f"expected octet-stream config download, got Content-Type={ctype!r}"
        )
    data = r.content
    if not data:
        raise ProtocolError("empty config body")
    return ConfigBackup(
        data=data,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _sanity_check_payload(data: bytes) -> None:
    """Reject payloads that cannot plausibly be a 2810 config file.

    Restore is the highest-risk write in the system: an uploaded garbage
    blob can leave the switch in an inconsistent state. Downloaded configs
    (see research/protocol/backup/download_config.md) are ASCII text whose
    first non-blank line starts with ``;`` (the
    ``; J9021A Configuration Editor`` header), so anything binary or
    headerless is refused before a single byte reaches the switch.
    """
    if not data.strip():
        raise ProtocolError("refusing to upload an empty config payload")
    if b"\x00" in data:
        raise ProtocolError(
            "refusing to upload config payload containing NUL bytes "
            "(not a .pcc text config)"
        )
    if not data.lstrip().startswith(b";"):
        raise ProtocolError(
            "refusing to upload config payload without the leading ';' "
            "config-editor header (see research/protocol/backup/"
            "download_config.md); pass force=True to override"
        )


@WRITE
async def upload_config(
    transport: ProcurveTransport,
    *,
    backup: ConfigBackup,
    configname: str = "Config",
    reboot_after: bool = False,
    force: bool = False,
) -> None:
    """Upload a ConfigBackup to the switch (restore).

    Sends `POST /cgi/upload` as multipart/form-data with:
      - configname: the named config slot to write (default "Config")
      - configfile: the backup bytes, filename="CONFIG.pcc"
      - reboot: omitted unless `reboot_after=True` (then value "on")
      - Uplo: literal "Upload" (submit-button name discriminator)

    On this switch the default `"Config"` name overwrites the active config.
    See research/protocol/backup/upload_config.md for the full contract.

    Safety additions:
      - the payload is sanity-checked before upload (must look like a .pcc
        text config); pass ``force=True`` to skip the check;
      - the response body is scanned for error markers. The firmware is
        known to return HTTP 200 with an error page instead of an HTTP
        error (see transport._check_status), and the research doc's success
        criterion is "200 with a body that does NOT contain 'error'" —
        so a suspicious body raises ProtocolError instead of silently
        reporting success. This fails safe: a false positive means the
        operator double-checks a restore that actually applied, rather
        than trusting one that didn't.
    """
    if not force:
        _sanity_check_payload(backup.data)
    data: dict[str, str] = {
        UPLOAD_CONFIGNAME_FIELD: configname,
        UPLOAD_SUBMIT_FIELD: "Upload",
    }
    if reboot_after:
        data[UPLOAD_REBOOT_FIELD] = "on"
    # --- FIX (2026-04-23): strip \r before upload ---
    # The /cgi/upload endpoint prepends an extra \r to every \n in the stored
    # file. Uploading with \r\n line endings results in stored \r\r\n, which
    # changes the downloaded SHA256 even though the operational config is
    # semantically unchanged. Stripping \r before upload lets the switch insert
    # its own \r\n and round-trip byte-identically.
    upload_data = backup.data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    files = {
        UPLOAD_CONFIGFILE_FIELD: (
            "CONFIG.pcc",
            upload_data,
            "application/octet-stream",
        ),
    }
    r = await transport.post(UPLOAD_PATH, data=data, files=files)
    if r.status_code != 200:
        raise ProtocolError(
            f"upload returned HTTP {r.status_code}: body={r.text[:200]!r}"
        )
    body_lower = r.text.lower()
    if "error" in body_lower:
        raise ProtocolError(
            "upload response contains an error marker — the switch likely "
            f"rejected the config: body={r.text[:200]!r}"
        )
