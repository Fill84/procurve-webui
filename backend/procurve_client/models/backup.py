"""Models for configuration backup download / upload."""
from __future__ import annotations

import hashlib
from enum import IntEnum

from pydantic import BaseModel, Field, model_validator


class ConfigSlot(IntEnum):
    """Config file slot on the switch (used for SOFTWARE images only; config
    uploads are keyed by name - see research/protocol/backup/upload_config.md)."""

    PRIMARY = 1
    SECONDARY = 2


class ConfigBackup(BaseModel):
    """A downloaded switch configuration snapshot."""

    text: str = Field(..., min_length=1)
    size: int = Field(..., gt=0)
    sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_consistency(self) -> ConfigBackup:
        if len(self.text.encode("ascii")) != self.size:
            raise ValueError("size does not match len(text.encode('ascii'))")
        if hashlib.sha256(self.text.encode("ascii")).hexdigest() != self.sha256:
            raise ValueError("sha256 does not match sha256(text)")
        return self

    @classmethod
    def from_text(cls, text: str) -> ConfigBackup:
        raw = text.encode("ascii")
        return cls(text=text, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
