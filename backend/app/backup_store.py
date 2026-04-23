"""Filesystem-backed store for switch configuration backups.

Layout under `root/`:
  backup_YYYYMMDDTHHMMSSZ.pcc         — raw .pcc bytes
  backup_YYYYMMDDTHHMMSSZ.pcc.meta.json — sidecar metadata (filename, created_at,
                                          size, sha256, trigger)

The store is synchronous — it only touches the filesystem.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from procurve_client.models.backup import ConfigBackup

Trigger = Literal["manual", "pre-write", "scheduled"]
_ALLOWED_TRIGGERS: frozenset[str] = frozenset({"manual", "pre-write", "scheduled"})

_SIDECAR_SUFFIX = ".meta.json"
_BACKUP_SUFFIX = ".pcc"

# Canonical filename pattern: backup_YYYYMMDDTHHMMSSZ[-N].pcc
# The regex forbids path separators (/, \), parent-dir segments (..) and
# absolute paths, so `self._root / filename` cannot escape the store root.
_FILENAME_PATTERN = re.compile(r"^backup_\d{8}T\d{6}Z(-\d+)?\.pcc$")


class InvalidBackupName(ValueError):  # noqa: N818 — part of the public API surface
    """Raised when a caller supplies a filename not matching the canonical format."""


class CorruptBackupError(ValueError):
    """Raised when a sidecar file exists but its JSON is malformed or invalid."""


def _validate_filename(filename: str) -> None:
    """Reject anything that isn't our canonical filename format.

    The regex prevents path separators (``/``, ``\\``), parent-dir segments
    (``..``), and absolute paths — so ``self._root / filename`` cannot escape
    the store root.
    """
    if not _FILENAME_PATTERN.fullmatch(filename):
        raise InvalidBackupName(f"invalid backup filename: {filename!r}")


class BackupMeta(BaseModel):
    """Sidecar metadata describing a stored backup."""

    filename: str
    created_at: datetime
    size: int
    sha256: str
    trigger: Trigger


def _now() -> datetime:
    """Current UTC timestamp. Split out so tests can monkeypatch it."""
    return datetime.now(UTC)


def _format_filename(ts: datetime) -> str:
    # backup_YYYYMMDDTHHMMSSZ.pcc — colon-free, UTC.
    return f"backup_{ts.strftime('%Y%m%dT%H%M%SZ')}{_BACKUP_SUFFIX}"


class BackupStore:
    """Filesystem-backed backup store under ``root``."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list(self) -> list[BackupMeta]:
        """Return all stored backups, newest (by created_at) first.

        Silently skips sidecars whose ``.pcc`` is missing (half-written) or
        whose JSON is corrupt — the individual-entry endpoints will surface
        the error for named lookups, but listing should stay resilient.
        """
        entries: list[BackupMeta] = []
        for sidecar in self._root.glob(f"*{_BACKUP_SUFFIX}{_SIDECAR_SUFFIX}"):
            # Ignore sidecars whose .pcc is missing (half-written).
            pcc = self._root / sidecar.name.removesuffix(_SIDECAR_SUFFIX)
            if not pcc.exists():
                continue
            try:
                entries.append(self._read_meta(sidecar))
            except CorruptBackupError:
                # Don't let one bad sidecar poison the whole listing.
                continue
        entries.sort(key=lambda m: m.created_at, reverse=True)
        return entries

    def get_meta(self, filename: str) -> BackupMeta:
        _validate_filename(filename)
        sidecar = self._sidecar_path(filename)
        pcc = self._pcc_path(filename)
        if not sidecar.exists():
            if pcc.exists():
                raise FileNotFoundError(f"backup metadata missing: {filename}")
            raise FileNotFoundError(f"backup not found: {filename}")
        return self._read_meta(sidecar)

    def load(self, filename: str) -> ConfigBackup:
        _validate_filename(filename)
        pcc = self._pcc_path(filename)
        if not pcc.exists():
            raise FileNotFoundError(f"backup not found: {filename}")
        return ConfigBackup.from_bytes(pcc.read_bytes())

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def save(self, backup: ConfigBackup, trigger: Trigger) -> BackupMeta:
        if trigger not in _ALLOWED_TRIGGERS:
            raise ValueError(
                f"trigger must be one of {sorted(_ALLOWED_TRIGGERS)}, got {trigger!r}"
            )
        ts = _now()
        filename = _format_filename(ts)
        pcc = self._pcc_path(filename)
        # If we happen to collide within the same second (rare), append a numeric
        # suffix. Keeps the sortable prefix and still respects the convention-ish.
        if pcc.exists():
            stem = pcc.stem
            n = 1
            while True:
                candidate = self._root / f"{stem}-{n}{_BACKUP_SUFFIX}"
                if not candidate.exists():
                    pcc = candidate
                    filename = pcc.name
                    break
                n += 1

        meta = BackupMeta(
            filename=filename,
            created_at=ts,
            size=backup.size,
            sha256=backup.sha256,
            trigger=trigger,
        )
        # Verify sha256 matches the provided data as a belt-and-suspenders
        # integrity check before we commit to disk.
        if hashlib.sha256(backup.data).hexdigest() != backup.sha256:
            raise ValueError("ConfigBackup.sha256 does not match sha256(data)")

        pcc.write_bytes(backup.data)
        self._write_meta(meta)
        return meta

    def delete(self, filename: str) -> None:
        _validate_filename(filename)
        pcc = self._pcc_path(filename)
        sidecar = self._sidecar_path(filename)
        if not pcc.exists() and not sidecar.exists():
            raise FileNotFoundError(f"backup not found: {filename}")
        if pcc.exists():
            pcc.unlink()
        if sidecar.exists():
            sidecar.unlink()

    # ------------------------------------------------------------------
    # Internals — callers MUST pass already-validated filenames.
    # ------------------------------------------------------------------

    def _pcc_path(self, filename: str) -> Path:
        return self._root / filename

    def _sidecar_path(self, filename: str) -> Path:
        return self._root / f"{filename}{_SIDECAR_SUFFIX}"

    def _write_meta(self, meta: BackupMeta) -> None:
        path = self._sidecar_path(meta.filename)
        path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def _read_meta(self, sidecar: Path) -> BackupMeta:
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            return BackupMeta.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorruptBackupError(
                f"backup metadata corrupt: {sidecar.name}"
            ) from exc


__all__ = [
    "BackupMeta",
    "BackupStore",
    "CorruptBackupError",
    "InvalidBackupName",
    "Trigger",
]
