"""Backups API (Task 2.4): list, create, download, diff, restore, delete.

Endpoints:
  GET    /api/v1/backups                       — list stored backups (newest first)
  POST   /api/v1/backups                       — download live config + save
  GET    /api/v1/backups/live-sha              — SHA256 of the live config
  GET    /api/v1/backups/{filename}/download   — stream the .pcc
  GET    /api/v1/backups/{filename}/diff       — unified diff vs live config
  POST   /api/v1/backups/{filename}/restore    — upload to switch (gated by READ_ONLY)
  DELETE /api/v1/backups/{filename}            — remove from store

Write safety: restore is the most destructive write in the app (it replaces
the entire active config), so it gets the FULL safety pattern used by
device-reset:

  1. `settings.read_only` gate *before* any switch I/O — 403 with
     `{"error": "read_only", ...}` when True (the default).
  2. `require_host_confirmation` — the caller must send the exact
     SWITCH_HOST in `confirm_switch_host`, same as device-reset.
  3. `write_with_autobackup` — the CURRENT live config is snapshotted as a
     `trigger="pre-write"` backup before the upload, so a wrong or stale
     restore always leaves a rollback point. The saved snapshot's filename
     is returned in the response as `pre_restore_backup`.

The lower-level `@WRITE` guard in procurve_client is a belt-and-suspenders
backstop, and `upload_config` itself now rejects suspicious payloads and
error-page responses (see procurve_client/operations/backup.py).
"""
from __future__ import annotations

import difflib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from app.backup_store import (
    BackupMeta,
    BackupStore,
    CorruptBackupError,
    InvalidBackupName,
    Trigger,
)
from app.deps import get_app_settings, get_backup_store, get_transport
from app.settings import Settings
from app.write_safety import require_host_confirmation, write_with_autobackup
from procurve_client.operations.backup import download_config, upload_config
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])


class CreateBackupRequest(BaseModel):
    """Public create endpoint: only "manual" is accepted. "pre-write" and
    "scheduled" are provenance markers reserved for server-internal callers
    of BackupStore.save — a client-supplied value could otherwise spoof the
    audit trail of whether the autobackup safety net actually fired."""

    trigger: Literal["manual"] = "manual"


class LiveShaResponse(BaseModel):
    sha256: str


# ---------------------------------------------------------------------------
# List + live-sha (declared before parameterized paths so routing is unambiguous)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[BackupMeta])
def list_backups(
    store: BackupStore = Depends(get_backup_store),  # noqa: B008 — FastAPI pattern
    _: ProcurveTransport = Depends(get_transport),  # noqa: B008 — auth gate
) -> list[BackupMeta]:
    return store.list()


@router.get("/live-sha", response_model=LiveShaResponse)
async def get_live_sha(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> LiveShaResponse:
    backup = await download_config(transport)
    return LiveShaResponse(sha256=backup.sha256)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("", response_model=BackupMeta, status_code=status.HTTP_201_CREATED)
async def create_backup(
    payload: CreateBackupRequest | None = None,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> BackupMeta:
    trigger: Trigger = payload.trigger if payload is not None else "manual"
    backup = await download_config(transport)
    return store.save(backup, trigger=trigger)


# ---------------------------------------------------------------------------
# Per-backup endpoints
# ---------------------------------------------------------------------------


@router.get("/{filename}/download")
def download_backup(
    filename: str,
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
    _: ProcurveTransport = Depends(get_transport),  # noqa: B008 — auth gate
) -> Response:
    try:
        backup = store.load(filename)
    except InvalidBackupName as exc:
        raise HTTPException(status_code=400, detail="invalid backup filename") from exc
    except CorruptBackupError as exc:
        raise HTTPException(status_code=500, detail="backup metadata corrupt") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup not found") from exc
    return Response(
        content=backup.data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{filename}/diff", response_class=PlainTextResponse)
async def diff_backup(
    filename: str,
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> PlainTextResponse:
    try:
        stored = store.load(filename)
    except InvalidBackupName as exc:
        raise HTTPException(status_code=400, detail="invalid backup filename") from exc
    except CorruptBackupError as exc:
        raise HTTPException(status_code=500, detail="backup metadata corrupt") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup not found") from exc
    live = await download_config(transport)
    diff_lines = difflib.unified_diff(
        stored.text.splitlines(keepends=True),
        live.text.splitlines(keepends=True),
        fromfile=filename,
        tofile="live",
    )
    return PlainTextResponse("".join(diff_lines), media_type="text/plain; charset=utf-8")


class RestoreRequest(BaseModel):
    """Restore confirmation. `confirm_switch_host` must equal settings.switch_host."""

    confirm_switch_host: str


@router.post("/{filename}/restore")
async def restore_backup(
    filename: str,
    body: RestoreRequest,
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> Response:
    # Safety gate order (all BEFORE any switch write):
    #   read_only -> host confirmation -> load backup -> pre-write snapshot
    # The read_only check keeps its flat JSON shape (the UI matches on
    # body.error === "read_only" to render the env-var hint).
    if settings.read_only:
        return JSONResponse(
            status_code=403,
            content={
                "error": "read_only",
                "detail": (
                    "Restore is disabled. Set READ_ONLY=false in .env to enable, "
                    "and only after verifying a current backup exists."
                ),
            },
        )
    require_host_confirmation(body.confirm_switch_host, settings)
    try:
        backup = store.load(filename)
    except InvalidBackupName as exc:
        raise HTTPException(status_code=400, detail="invalid backup filename") from exc
    except CorruptBackupError as exc:
        raise HTTPException(status_code=500, detail="backup metadata corrupt") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup not found") from exc

    pre_restore: list[BackupMeta] = []
    await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: upload_config(transport, backup=backup),
        on_backup=pre_restore.append,
    )
    return JSONResponse(
        status_code=200,
        content={
            "status": "restored",
            "filename": filename,
            "sha256": backup.sha256,
            # Rollback point: the live config as it was immediately before
            # this restore, saved as a trigger="pre-write" backup.
            "pre_restore_backup": pre_restore[0].filename if pre_restore else None,
        },
    )


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backup(
    filename: str,
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
    _: ProcurveTransport = Depends(get_transport),  # noqa: B008 — auth gate
) -> Response:
    try:
        store.delete(filename)
    except InvalidBackupName as exc:
        raise HTTPException(status_code=400, detail="invalid backup filename") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__: list[str] = ["router"]
