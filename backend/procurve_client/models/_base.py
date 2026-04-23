"""Shared Pydantic helpers for procurve_client models."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_MAC_HEX_ONLY = re.compile(r"^[0-9A-Fa-f]{12}$")
_MAC_SEPARATED = re.compile(r"^[0-9A-Fa-f]{2}([:\-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}$")


class MacAddress(BaseModel):
    """Normalized MAC address in uppercase colon-separated form."""

    value: str

    @field_validator("value")
    @classmethod
    def _normalize(cls, v: str) -> str:
        if _MAC_SEPARATED.match(v):
            hex_only = v.replace(":", "").replace("-", "")
        elif _MAC_HEX_ONLY.match(v):
            hex_only = v
        else:
            raise ValueError(f"not a valid MAC address: {v!r}")
        hex_only = hex_only.upper()
        return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


class PortNumber(BaseModel):
    """Port number 1..24 for the 2810-24G chassis."""

    value: int = Field(..., ge=1, le=24)


class VlanId(BaseModel):
    """VLAN ID 1..4094."""

    value: int = Field(..., ge=1, le=4094)
