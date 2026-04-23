"""Tests for BackupStore — filesystem-backed backup store.

All tests use pytest's `tmp_path` fixture; no real filesystem state leaks
between tests.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.backup_store import (
    BackupMeta,
    BackupStore,
    CorruptBackupError,
    InvalidBackupName,
)
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


# ---------------------------------------------------------------------------
# Path-traversal / filename validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "/etc/passwd",
        "C:\\Windows\\System32",
        "normal.txt",                         # wrong extension
        "backup_bad.pcc",                     # wrong prefix pattern
        "backup_20260423T120000Z.pcc/../x",   # embedded separator
        "",
    ],
)
def test_load_rejects_non_canonical_filenames(tmp_path: Path, bad_name: str) -> None:
    store = BackupStore(tmp_path)
    with pytest.raises(InvalidBackupName):
        store.load(bad_name)


def test_delete_rejects_non_canonical_filenames(tmp_path: Path) -> None:
    store = BackupStore(tmp_path)
    with pytest.raises(InvalidBackupName):
        store.delete("../../etc/passwd")


def test_get_meta_rejects_non_canonical_filenames(tmp_path: Path) -> None:
    store = BackupStore(tmp_path)
    with pytest.raises(InvalidBackupName):
        store.get_meta("../../etc/passwd")


# ---------------------------------------------------------------------------
# Collision suffixing
# ---------------------------------------------------------------------------


def test_save_appends_suffix_on_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Freeze the clock so both saves compute the same base filename.
    import app.backup_store as store_mod

    fixed = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(store_mod, "_now", lambda: fixed)

    store = BackupStore(tmp_path)
    backup_a = ConfigBackup.from_bytes(b"alpha content here\n")
    backup_b = ConfigBackup.from_bytes(b"beta content here\n")

    meta_a = store.save(backup_a, trigger="manual")
    meta_b = store.save(backup_b, trigger="manual")

    assert meta_a.filename == "backup_20260423T120000Z.pcc"
    assert meta_b.filename == "backup_20260423T120000Z-1.pcc"
    names = {m.filename for m in store.list()}
    assert names == {meta_a.filename, meta_b.filename}


def test_save_appends_incrementing_suffix_on_repeated_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Three saves at the same instant should yield -0 (no suffix), -1, -2.
    import app.backup_store as store_mod

    fixed = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(store_mod, "_now", lambda: fixed)

    store = BackupStore(tmp_path)
    metas = [
        store.save(ConfigBackup.from_bytes(f"cfg-{i}\n".encode()), trigger="manual")
        for i in range(3)
    ]
    names = [m.filename for m in metas]
    assert names == [
        "backup_20260423T120000Z.pcc",
        "backup_20260423T120000Z-1.pcc",
        "backup_20260423T120000Z-2.pcc",
    ]


# ---------------------------------------------------------------------------
# Corrupt / missing sidecar handling
# ---------------------------------------------------------------------------


def test_get_meta_missing_sidecar_when_pcc_present_raises_file_not_found(
    tmp_path: Path,
) -> None:
    # Simulate a half-written backup: .pcc on disk but no sidecar.
    store = BackupStore(tmp_path)
    filename = "backup_20260423T120000Z.pcc"
    (tmp_path / filename).write_bytes(b"orphan\n")
    with pytest.raises(FileNotFoundError, match="metadata missing"):
        store.get_meta(filename)


def test_get_meta_corrupt_json_raises_corrupt_backup_error(tmp_path: Path) -> None:
    store = BackupStore(tmp_path)
    filename = "backup_20260423T120000Z.pcc"
    (tmp_path / filename).write_bytes(b"data\n")
    (tmp_path / f"{filename}.meta.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CorruptBackupError):
        store.get_meta(filename)


def test_list_skips_corrupt_sidecar(tmp_path: Path) -> None:
    # A well-formed pair plus a corrupt sidecar: listing shows only the good one.
    store = BackupStore(tmp_path)
    good = store.save(_fake_backup(b"ok\n"), trigger="manual")
    bad_name = "backup_20990101T000000Z.pcc"
    (tmp_path / bad_name).write_bytes(b"bytes\n")
    (tmp_path / f"{bad_name}.meta.json").write_text(
        "not-json-at-all", encoding="utf-8"
    )
    listed = store.list()
    assert [m.filename for m in listed] == [good.filename]
