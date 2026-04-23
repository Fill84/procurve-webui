"""Shared fixtures for operation-level tests."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to research/fixtures/ — live-captured responses from Phase 0."""
    return Path(__file__).resolve().parents[3] / "research" / "fixtures"


@pytest.fixture
def reference_backup_text(fixtures_dir: Path) -> str:
    path = fixtures_dir / "download_config.response.txt"
    return path.read_text(encoding="ascii", newline="")
