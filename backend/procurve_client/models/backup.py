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
    """A downloaded switch configuration snapshot.

    Internally stores bytes (the authoritative wire form). The `text` property
    is a convenience latin-1 view that always round-trips to the same bytes,
    regardless of encoding.
    """

    model_config = {"arbitrary_types_allowed": True}

    data: bytes = Field(..., min_length=1)
    size: int = Field(..., gt=0)
    sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_consistency(self) -> ConfigBackup:
        if len(self.data) != self.size:
            raise ValueError("size does not match len(data)")
        if hashlib.sha256(self.data).hexdigest() != self.sha256:
            raise ValueError("sha256 does not match sha256(data)")
        return self

    @classmethod
    def from_bytes(cls, data: bytes) -> ConfigBackup:
        return cls(data=data, size=len(data), sha256=hashlib.sha256(data).hexdigest())

    @classmethod
    def from_text(cls, text: str) -> ConfigBackup:
        """Build from text. Encodes as latin-1 so every code point round-trips
        to the same byte sequence (ASCII is unchanged; non-ASCII survives)."""
        # latin-1 is chosen deliberately: every byte 0x00-0xFF maps 1:1 and
        # round-trips. ASCII configs are unaffected; non-ASCII survives intact.
        return cls.from_bytes(text.encode("latin-1"))

    @property
    def text(self) -> str:
        """latin-1 decoded view of the backup bytes. Guaranteed byte-round-trippable."""
        return self.data.decode("latin-1")
