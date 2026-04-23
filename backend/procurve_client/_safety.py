"""Safety decorators: @READ (marker) and @WRITE (marker + READ_ONLY enforcement)."""
from __future__ import annotations

import functools
import os
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from procurve_client.errors import WriteDisabledError

P = ParamSpec("P")
R = TypeVar("R")

_READ_ATTR = "__procurve_read__"
_WRITE_ATTR = "__procurve_write__"


def _read_only_enabled() -> bool:
    """Return True unless READ_ONLY is explicitly set to a falsey value."""
    raw = os.environ.get("READ_ONLY", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def READ(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:  # noqa: N802, UP047
    """Mark an async operation as read-only. Runtime behavior is a no-op."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await func(*args, **kwargs)

    setattr(wrapper, _READ_ATTR, True)
    return wrapper


def WRITE(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:  # noqa: N802, UP047
    """Mark an async operation as writing. Blocked when READ_ONLY is enabled."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if _read_only_enabled():
            raise WriteDisabledError(operation=func.__name__)
        return await func(*args, **kwargs)

    setattr(wrapper, _WRITE_ATTR, True)
    return wrapper


def is_read(func: Any) -> bool:
    return bool(getattr(func, _READ_ATTR, False))


def is_write(func: Any) -> bool:
    return bool(getattr(func, _WRITE_ATTR, False))
