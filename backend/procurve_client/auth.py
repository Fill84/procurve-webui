"""Authentication strategies for ProcurveTransport."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol


class AuthStrategy(Protocol):
    def headers(self) -> dict[str, str]:
        """Return headers to attach to every request."""


@dataclass(frozen=True)
class NoneAuth:
    """No authentication (current switch default: blank user/password)."""

    def headers(self) -> dict[str, str]:
        return {}


@dataclass(frozen=True)
class BasicAuth:
    """HTTP Basic authentication."""

    username: str
    password: str

    def headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
