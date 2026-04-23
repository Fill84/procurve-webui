"""Backups API (Task 2.4): list, create, download, diff, restore, delete.

Endpoints:
  GET    /api/v1/backups                       — list stored backups (newest first)
  POST   /api/v1/backups                       — download live config + save
  GET    /api/v1/backups/live-sha              — SHA256 of the live config
  GET    /api/v1/backups/{filename}/download   — stream the .pcc
  GET    /api/v1/backups/{filename}/diff       — unified diff vs live config
  POST   /api/v1/backups/{filename}/restore    — upload to switch (gated by READ_ONLY)
  DELETE /api/v1/backups/{filename}            — remove from store

Write safety: the restore endpoint checks `settings.read_only` *before*
delegating to `upload_config`. When read_only is True (the default), we
return 403 with `{"error": "read_only", ...}` and do NOT invoke the write
operation. The lower-level `@WRITE` guard in procurve_client is a belt-and-
suspenders backstop.
"""
from __future__ import annotations

import difflib

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
from procurve_client.operations.backup import download_config, upload_config
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/backups", tags=["backups"])


class CreateBackupRequest(BaseModel):
    trigger: Trigger = "manual"


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


@router.post("/{filename}/restore")
async def restore_backup(
    filename: str,
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> Response:
    # Safety: settings.read_only gate runs BEFORE we even load the backup so we
    # cannot accidentally touch the switch. The @WRITE decorator on
    # upload_config is a backstop for the same condition via env.
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
    try:
        backup = store.load(filename)
    except InvalidBackupName as exc:
        raise HTTPException(status_code=400, detail="invalid backup filename") from exc
    except CorruptBackupError as exc:
        raise HTTPException(status_code=500, detail="backup metadata corrupt") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="backup not found") from exc
    await upload_config(transport, backup=backup)
    return JSONResponse(
        status_code=200,
        content={"status": "restored", "filename": filename, "sha256": backup.sha256},
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
