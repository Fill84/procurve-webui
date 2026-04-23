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
    text = r.text
    if not text:
        raise ProtocolError("empty config body")
    raw = text.encode("ascii")
    return ConfigBackup(
        text=text,
        size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


@WRITE
async def upload_config(
    transport: ProcurveTransport,
    *,
    backup: ConfigBackup,
    configname: str = "Config",
    reboot_after: bool = False,
) -> None:
    """Upload a ConfigBackup to the switch (restore).

    Sends `POST /cgi/upload` as multipart/form-data with:
      - configname: the named config slot to write (default "Config")
      - configfile: the backup bytes, filename="CONFIG.pcc"
      - reboot: omitted unless `reboot_after=True` (then value "on")
      - Uplo: literal "Upload" (submit-button name discriminator)

    On this switch the default `"Config"` name overwrites the active config.
    See research/protocol/backup/upload_config.md for the full contract.
    """
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
    upload_text = backup.text.replace("\r\n", "\n").replace("\r", "\n")
    files = {
        UPLOAD_CONFIGFILE_FIELD: (
            "CONFIG.pcc",
            upload_text.encode("ascii"),
            "application/octet-stream",
        ),
    }
    r = await transport.post(UPLOAD_PATH, data=data, files=files)
    if r.status_code != 200:
        raise ProtocolError(
            f"upload returned HTTP {r.status_code}: body={r.text[:200]!r}"
        )
