"""Backup download (read) and restore (write) operations.

Contracts from Phase 0:
- Download: GET /cgi/configfile?idx={slot}&fg={slot}&D1=Download
- Upload:   POST /cgi/upload (multipart; fields: configname, configfile, [reboot], Uplo)

See research/protocol/backup/{download_config,upload_config}.md.
"""
from __future__ import annotations

import hashlib

from procurve_client._safety import READ
from procurve_client.errors import ProtocolError
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.transport import ProcurveTransport

_DOWNLOAD_PATH = "/cgi/configfile"


@READ
async def download_config(
    transport: ProcurveTransport,
    *,
    slot: ConfigSlot = ConfigSlot.PRIMARY,
) -> ConfigBackup:
    """Download the current running-config from the switch."""
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


# upload_config (write) added in Task 1.10.
