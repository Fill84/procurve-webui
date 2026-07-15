"""Safety decorators: @READ (marker) and @WRITE (marker + READ_ONLY enforcement)."""
from __future__ import annotations

import functools
import os
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from pydantic import ValidationError

from procurve_client.errors import (
    ParseError,
    ProcurveError,
    SchemaError,
    WriteDisabledError,
)

P = ParamSpec("P")
R = TypeVar("R")

_READ_ATTR = "__procurve_read__"
_WRITE_ATTR = "__procurve_write__"


def _read_only_enabled() -> bool:
    """Return True unless READ_ONLY is explicitly set to a falsey value."""
    raw = os.environ.get("READ_ONLY", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


async def _run_typed[**TP, TR](
    func: Callable[TP, Awaitable[TR]], *args: TP.args, **kwargs: TP.kwargs
) -> TR:
    """Run an operation, translating stray parse crashes into typed errors.

    Operations parse untrusted switch bodies; most conversion sites raise
    `ParseError` explicitly, but a missed one (short row → IndexError,
    model construction from garbage tokens → pydantic ValidationError)
    used to escape as a raw exception → generic 500. Typed `ProcurveError`
    subclasses pass through untouched.
    """
    try:
        return await func(*args, **kwargs)
    except ProcurveError:
        raise
    except ValidationError as exc:
        raise SchemaError(
            f"{func.__name__}: switch response violated the expected "
            f"schema: {exc.errors()[0].get('msg', 'validation error')}"
        ) from exc
    except IndexError as exc:
        raise ParseError(
            f"{func.__name__}: switch response was shorter than expected"
        ) from exc


def READ(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:  # noqa: N802, UP047
    """Mark an async operation as read-only. Enforces typed parse errors."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await _run_typed(func, *args, **kwargs)

    setattr(wrapper, _READ_ATTR, True)
    return wrapper


def WRITE(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:  # noqa: N802, UP047
    """Mark an async operation as writing. Blocked when READ_ONLY is enabled."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if _read_only_enabled():
            raise WriteDisabledError(operation=func.__name__)
        return await _run_typed(func, *args, **kwargs)

    setattr(wrapper, _WRITE_ATTR, True)
    return wrapper


def is_read(func: Any) -> bool:
    return bool(getattr(func, _READ_ATTR, False))


def is_write(func: Any) -> bool:
    return bool(getattr(func, _WRITE_ATTR, False))
