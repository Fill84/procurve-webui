"""Unit tests for the @READ / @WRITE safety decorators."""
import pytest
from pydantic import BaseModel

from procurve_client._safety import READ, WRITE, is_read, is_write
from procurve_client.errors import (
    OperationError,
    ParseError,
    SchemaError,
    WriteDisabledError,
)


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


class _IntModel(BaseModel):
    n: int


@READ
async def _read_bad_schema() -> _IntModel:
    return _IntModel(n="garbage")  # type: ignore[arg-type]


@READ
async def _read_short_row() -> str:
    row: list[str] = []
    return row[3]


@READ
async def _read_typed_error() -> None:
    raise OperationError("switch said no")


async def test_read_translates_validation_error_to_schema_error():
    """Model construction from garbage tokens must surface as SchemaError,
    not a raw pydantic ValidationError → generic 500 (L11)."""
    with pytest.raises(SchemaError, match="_read_bad_schema"):
        await _read_bad_schema()


async def test_read_translates_index_error_to_parse_error():
    with pytest.raises(ParseError, match="shorter than expected"):
        await _read_short_row()


async def test_read_passes_typed_errors_through_unchanged():
    with pytest.raises(OperationError, match="switch said no"):
        await _read_typed_error()


async def test_write_translates_parse_crashes_too(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")

    @WRITE
    async def _write_bad_schema() -> _IntModel:
        return _IntModel(n="garbage")  # type: ignore[arg-type]

    with pytest.raises(SchemaError):
        await _write_bad_schema()


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
