"""Unit tests for app settings."""
import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_settings_reads_switch_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWITCH_HOST", "10.0.0.1")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    s = Settings()
    assert s.switch_host == "10.0.0.1"


def test_settings_requires_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setenv("SWITCH_HOST", "10.0.0.1")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults_match_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWITCH_HOST", "10.0.0.1")
    monkeypatch.setenv("SESSION_SECRET", "a" * 32)
    s = Settings()
    assert s.switch_port == 80
    assert s.host == "127.0.0.1"
    assert s.port == 8080
    assert s.read_only is True
    assert s.session_ttl_hours == 8
    assert s.metrics_enabled is False
