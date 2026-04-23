"""Operation registry. Import every tab's operations and build READ/WRITE indexes."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from procurve_client._safety import is_read, is_write
from procurve_client.operations import (
    backup,
    configuration,
    diagnostics,
    identity,
    security,
    stacking,
    status,
    support,
    vlan,
)


def _discover(module: Any) -> list[Callable[..., Any]]:
    """Return every @READ / @WRITE-decorated function exported by a module."""
    out: list[Callable[..., Any]] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and (is_read(obj) or is_write(obj)):
            out.append(obj)
    return out


_MODULES = [
    backup,
    identity,
    status,
    configuration,
    vlan,
    stacking,
    security,
    diagnostics,
    support,
]

ALL_OPERATIONS: list[Callable[..., Any]] = [op for m in _MODULES for op in _discover(m)]
READ_OPERATIONS: list[Callable[..., Any]] = [op for op in ALL_OPERATIONS if is_read(op)]
WRITE_OPERATIONS: list[Callable[..., Any]] = [op for op in ALL_OPERATIONS if is_write(op)]
