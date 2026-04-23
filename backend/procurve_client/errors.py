"""Typed exception hierarchy for the procurve_client library."""
from __future__ import annotations

from typing import Any


class ProcurveError(Exception):
    """Root of the procurve_client error hierarchy."""


class TransportError(ProcurveError):
    """Network, timeout, DNS, or socket-level failure."""

    def __init__(self, message: str, *, host: str | None = None) -> None:
        super().__init__(message)
        self.host = host


class AuthError(ProcurveError):
    """Authentication failure (401/403 or auth-redirect)."""


class ProtocolError(ProcurveError):
    """Switch returned a response we could not handle as expected."""


class ParseError(ProtocolError):
    """Low-level parser could not read the response body."""


class SchemaError(ProtocolError):
    """Response parsed but violated the Pydantic schema."""


class OperationError(ProcurveError):
    """Switch explicitly rejected the operation."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.detail = detail or {}


class WriteDisabledError(ProcurveError):
    """A @WRITE operation was invoked while READ_ONLY is enabled."""

    def __init__(self, *, operation: str) -> None:
        super().__init__(
            f"Write operation {operation!r} is disabled (READ_ONLY=true). "
            f"Set READ_ONLY=false to allow."
        )
        self.operation = operation
