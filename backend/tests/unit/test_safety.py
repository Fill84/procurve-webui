"""Unit tests for the @READ / @WRITE safety decorators."""
import pytest

from procurve_client._safety import READ, WRITE, is_read, is_write
from procurve_client.errors import WriteDisabledError


@READ
async def sample_read() -> str:
    return "ok"


@WRITE
async def sample_write() -> str:
    return "wrote"


async def test_read_decorator_is_noop():
    assert await sample_read() == "ok"
    assert is_read(sample_read) is True
    assert is_write(sample_read) is False


async def test_write_runs_when_read_only_false(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    assert await sample_write() == "wrote"
    assert is_write(sample_write) is True


async def test_write_blocked_when_read_only_true(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "true")
    with pytest.raises(WriteDisabledError) as exc_info:
        await sample_write()
    assert exc_info.value.operation == "sample_write"


async def test_write_blocked_when_read_only_unset(monkeypatch):
    # default: safer choice is to block writes
    monkeypatch.delenv("READ_ONLY", raising=False)
    with pytest.raises(WriteDisabledError):
        await sample_write()


async def test_write_read_only_accepts_various_falsey(monkeypatch):
    # Only "false" / "0" / "no" / "off" should enable writes.
    for value in ("false", "FALSE", "0", "no", "off"):
        monkeypatch.setenv("READ_ONLY", value)
        assert await sample_write() == "wrote", f"{value!r} should allow writes"

    # "" and other strings should block (default-safe).
    for value in ("", "true", "TRUE", "yes", "on", "1"):
        monkeypatch.setenv("READ_ONLY", value)
        with pytest.raises(WriteDisabledError):
            await sample_write()
