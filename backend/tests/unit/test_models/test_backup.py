"""Unit tests for the ConfigBackup model."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from procurve_client.models.backup import ConfigBackup, ConfigSlot


def test_config_backup_from_text_computes_hash_and_size():
    text = "; J9021A Configuration Editor; Created on release #N.11.78\r\nhostname \"X\"\r\n"
    cb = ConfigBackup.from_text(text)
    assert cb.text == text
    assert cb.size == len(text.encode("ascii"))
    # sha256 is 64 hex chars lowercase
    assert len(cb.sha256) == 64
    assert all(c in "0123456789abcdef" for c in cb.sha256)


def test_config_backup_slot_values():
    assert ConfigSlot.PRIMARY.value == 1
    assert ConfigSlot.SECONDARY.value == 2


def test_config_backup_reference_sha_matches_known():
    # Fixture recorded 2026-04-23 from the live switch.
    expected = "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11"
    fixture = (
        Path(__file__).resolve().parents[4]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    text = fixture.read_text(encoding="ascii", newline="")
    cb = ConfigBackup.from_text(text)
    assert cb.size == 2904
    assert cb.sha256 == expected


def test_config_backup_rejects_empty():
    with pytest.raises(ValidationError):
        ConfigBackup(text="", size=0, sha256="")


def test_config_backup_rejects_size_mismatch():
    with pytest.raises(ValidationError):
        ConfigBackup(
            text="hello",
            size=99,
            sha256="2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )


def test_config_backup_rejects_sha_mismatch():
    with pytest.raises(ValidationError):
        ConfigBackup(
            text="hello",
            size=5,
            sha256="0" * 64,
        )
