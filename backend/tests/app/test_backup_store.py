"""Tests for BackupStore — filesystem-backed backup store.

All tests use pytest's `tmp_path` fixture; no real filesystem state leaks
between tests.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.backup_store import BackupMeta, BackupStore
from procurve_client.models.backup import ConfigBackup


def _fake_backup(payload: bytes = b"hostname foo\n") -> ConfigBackup:
    return ConfigBackup.from_bytes(payload)


def test_list_on_empty_dir_returns_empty_list(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    assert store.list() == []


def test_save_and_list(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    first = store.save(_fake_backup(b"first\n"), trigger="manual")
    second = store.save(_fake_backup(b"second\n"), trigger="pre-write")
    listed = store.list()
    assert len(listed) == 2
    # Newest first.
    assert listed[0].filename == second.filename
    assert listed[1].filename == first.filename
    assert listed[0].created_at >= listed[1].created_at


def test_save_writes_pcc_and_meta_sidecar(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    meta = store.save(_fake_backup(b"data\n"), trigger="manual")
    pcc = tmp_path / meta.filename
    sidecar = tmp_path / f"{meta.filename}.meta.json"
    assert pcc.exists()
    assert sidecar.exists()
    assert pcc.read_bytes() == b"data\n"
    parsed = json.loads(sidecar.read_text(encoding="utf-8"))
    assert parsed["filename"] == meta.filename
    assert parsed["size"] == 5
    assert parsed["trigger"] == "manual"
    assert re.fullmatch(r"[0-9a-f]{64}", parsed["sha256"])


def test_load_round_trips_bytes(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    payload = b"interface 1\n   name foo\nexit\n"
    meta = store.save(_fake_backup(payload), trigger="manual")
    loaded = store.load(meta.filename)
    assert loaded.data == payload
    assert loaded.size == len(payload)
    assert loaded.sha256 == meta.sha256


def test_delete_removes_both_files(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    meta = store.save(_fake_backup(b"x\n"), trigger="manual")
    pcc = tmp_path / meta.filename
    sidecar = tmp_path / f"{meta.filename}.meta.json"
    assert pcc.exists() and sidecar.exists()
    store.delete(meta.filename)
    assert not pcc.exists()
    assert not sidecar.exists()
    assert store.list() == []


def test_filename_format_matches_convention(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    meta = store.save(_fake_backup(b"y\n"), trigger="scheduled")
    # backup_YYYYMMDDTHHMMSSZ.pcc
    assert re.fullmatch(r"backup_\d{8}T\d{6}Z\.pcc", meta.filename)


def test_get_meta_returns_same_as_list_entry(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    meta = store.save(_fake_backup(b"z\n"), trigger="manual")
    got = store.get_meta(meta.filename)
    assert got == meta


def test_get_meta_missing_raises(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        store.get_meta("backup_00000000T000000Z.pcc")


def test_load_missing_raises(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load("backup_00000000T000000Z.pcc")


def test_delete_missing_raises(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        store.delete("backup_00000000T000000Z.pcc")


def test_save_rejects_unknown_trigger(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    with pytest.raises(ValueError):
        store.save(_fake_backup(b"a\n"), trigger="bogus")  # type: ignore[arg-type]


def test_list_ignores_unrelated_files(tmp_path: Path) -> None:
    # Write some junk that isn't a backup; listing must not break.
    (tmp_path / "README.txt").write_text("notes")
    (tmp_path / "stray.pcc").write_bytes(b"no sidecar")
    store = BackupStore(root=tmp_path)
    meta = store.save(_fake_backup(b"b\n"), trigger="manual")
    listed = store.list()
    assert [m.filename for m in listed] == [meta.filename]


def test_list_returns_backup_meta_objects(tmp_path: Path) -> None:
    store = BackupStore(root=tmp_path)
    store.save(_fake_backup(b"c\n"), trigger="manual")
    listed = store.list()
    assert all(isinstance(m, BackupMeta) for m in listed)


def test_root_is_created_if_missing(tmp_path: Path) -> None:
    root = tmp_path / "does" / "not" / "exist"
    store = BackupStore(root=root)
    assert root.is_dir()
    store.save(_fake_backup(b"d\n"), trigger="manual")
    assert len(store.list()) == 1
