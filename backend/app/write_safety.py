"""Universal safety wrapper for write endpoints.

Every write route in Phase 3 goes through ``write_with_autobackup`` so that:

1. ``settings.read_only = True`` returns 403 *before* any switch I/O.
2. :func:`download_config` is called first and saved as a
   ``trigger="pre-write"`` backup.
3. The write itself runs only after the backup is persisted on disk.
4. On backup failure the write is aborted; the user never loses a rollback
   point.

The helper exposes three public callables:

* :func:`require_writable` — raises ``403`` when the backend is in read-only
  mode. Invoked implicitly by :func:`write_with_autobackup`, so route
  handlers generally do not need to call it directly.
* :func:`require_host_confirmation` — raises ``400`` when the user-supplied
  ``confirm_switch_host`` value does not match ``settings.switch_host``
  exactly. Call this from the route handler *before*
  :func:`write_with_autobackup` so a mistyped confirmation short-circuits
  before any switch I/O.
* :func:`write_with_autobackup` — the main entry point: gates on
  ``read_only``, downloads + stores a pre-write backup, then runs the caller
  supplied ``write`` coroutine.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import HTTPException

from app.backup_store import BackupMeta, BackupStore
from app.settings import Settings
from procurve_client.operations.backup import download_config
from procurve_client.transport import ProcurveTransport

__all__ = [
    "require_host_confirmation",
    "require_writable",
    "write_with_autobackup",
]


def require_writable(settings: Settings) -> None:
    """Raise ``HTTPException(403)`` when the image is in read-only mode."""
    if settings.read_only:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "read_only",
                "detail": (
                    "Writes are disabled. Set READ_ONLY=false in the backend "
                    "environment to enable."
                ),
            },
        )


def require_host_confirmation(
    confirmation: str | None, settings: Settings
) -> None:
    """Raise ``HTTPException(400)`` when the caller did not type the exact
    switch host.

    The comparison is strict (after ``.strip()``): anything other than the
    current ``settings.switch_host`` rejects. ``None`` and empty strings also
    reject so that a missing confirmation field cannot bypass the gate.
    """
    if not confirmation or confirmation.strip() != settings.switch_host:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "host_mismatch",
                "detail": (
                    "confirm_switch_host must equal the current SWITCH_HOST "
                    f"({settings.switch_host!r})."
                ),
            },
        )


async def write_with_autobackup[T](
    *,
    settings: Settings,
    store: BackupStore,
    transport: ProcurveTransport,
    write: Callable[[], Awaitable[T]],
    on_backup: Callable[[BackupMeta], None] | None = None,
) -> T:
    """Run ``write()`` only after a pre-write backup has been saved.

    ``require_writable(settings)`` is called internally — callers do **not**
    need to call it separately. This keeps the write-gate ordering in one
    place so every Phase 3 write route gets the same behaviour automatically.

    ``on_backup`` (optional) receives the saved pre-write :class:`BackupMeta`
    before the write runs — used by routes that want to surface the rollback
    point to the user (e.g. restore returns it so the UI can offer an
    "undo restore" affordance).

    If :func:`download_config` or :meth:`BackupStore.save` raises, the
    ``write`` coroutine is never scheduled and no partial state is left
    behind: the caller is responsible for surfacing the error, but the switch
    remains untouched.
    """
    log = structlog.get_logger()
    require_writable(settings)
    backup = await download_config(transport)
    meta = store.save(backup, trigger="pre-write")
    log.info(
        "pre_write_backup_saved", filename=meta.filename, sha256=meta.sha256
    )
    if on_backup is not None:
        on_backup(meta)
    try:
        result = await write()
    except Exception as exc:
        log.warning(
            "switch_write_failed",
            error=type(exc).__name__,
            detail=str(exc)[:200],
            rollback_backup=meta.filename,
        )
        raise
    log.info("switch_write_completed", rollback_backup=meta.filename)
    return result
