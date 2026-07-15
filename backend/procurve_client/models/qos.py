"""Models for QoS (Class of Service) sub-tab operations.

Sources:
- research/protocol/configuration/get_cos_appt.md
- research/protocol/configuration/set_cos_appt.md
- research/protocol/configuration/get_cos_userpri.md
- research/protocol/configuration/set_cos_userpri.md
- research/protocol/configuration/set_costos_mode.md
- research/protocol/configuration/get_cos_vlanpri.md
- research/protocol/configuration/set_cos_vlanpri.md
- research/protocol/configuration/get_dscptable.md
- research/protocol/configuration/set_dscptable.md
- research/protocol/configuration/get_diffserv.md
- research/protocol/configuration/set_diffserv.md
- research/protocol/configuration/set_cosproto.md

QoS CGIs return bare-row tilde streams (GenericList-driven — no sentinel).
Write endpoints return unverified bodies; callers rely on HTTP 200.
"""
from __future__ import annotations

from enum import IntEnum
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _domain_or_sentinel(name: str, value: int, upper: int) -> int:
    """Allow 0..upper plus the legacy 255 "No override" sentinel.

    The legacy <select> lists offer only these values; anything else must
    never reach the switch (audit F3).
    """
    if value != 255 and not (0 <= value <= upper):
        raise ValueError(f"{name} must be 0..{upper} or 255 (No override)")
    return value

# ---- Shared enums -------------------------------------------------------

class ApplyPolicy(IntEnum):
    """QoS apply-policy selector shared by set_cos_appt and set_cos_userpri."""

    NO_OVERRIDE = 1
    P_8021 = 2
    DSCP = 3


class CosTosMode(IntEnum):
    """Switch-wide Type-of-Service interpretation mode (set_costos_mode)."""

    DISABLED = 1
    IP_PRECEDENCE = 2
    DIFFSERV = 3


# ---- get_cos_appt / set_cos_appt ---------------------------------------

class CosAppEntry(BaseModel):
    """One row of /cgi/cosapp — an application → priority mapping."""

    application_name: str
    port_number: int = Field(..., ge=1, le=65535)
    type: Literal["TCP", "UDP"]
    dscp: str
    priority: str


class CosAppList(BaseModel):
    entries: list[CosAppEntry] = Field(default_factory=list)


class SetCosApptRequest(BaseModel):
    """Parameters for /cgi/cosappf. Cross-frame quirk — see protocol doc."""

    action: Literal["Add", "Replace", "Delete"]
    app_id: int = Field(..., ge=0, le=58)
    protocol: Literal["TCP", "UDP"]
    port: int | None = Field(default=None, ge=1, le=65535)
    policy_mode: ApplyPolicy = ApplyPolicy.NO_OVERRIDE
    dscp: int | None = Field(default=None, ge=0, le=63)
    priority_8021p: int | None = Field(default=None, ge=0, le=7)

    @model_validator(mode="after")
    def _consistency(self) -> SetCosApptRequest:
        if self.app_id == 0 and self.port is None:
            raise ValueError("port required when app_id=0 (User defined)")
        if self.policy_mode == ApplyPolicy.DSCP and self.dscp is None:
            raise ValueError("dscp required for DSCP policy")
        if self.policy_mode == ApplyPolicy.P_8021 and self.priority_8021p is None:
            raise ValueError("priority_8021p required for 802.1p policy")
        return self


# ---- get_cos_userpri / set_cos_userpri ---------------------------------

class CosUserEntry(BaseModel):
    """One row of /cgi/cosuser — per-device QoS mapping."""

    ip_address: IPv4Address
    dscp_policy: str
    priority: str


class CosUserList(BaseModel):
    entries: list[CosUserEntry] = Field(default_factory=list)


class SetCosUserPriRequest(BaseModel):
    action: Literal["Add", "Replace", "Delete"]
    address: IPv4Address
    policy_mode: ApplyPolicy = ApplyPolicy.NO_OVERRIDE
    priority_8021p: int | None = Field(default=None, ge=0, le=7)
    dscp: int | None = Field(default=None, ge=0, le=63)

    @model_validator(mode="after")
    def _consistency(self) -> SetCosUserPriRequest:
        if self.policy_mode == ApplyPolicy.DSCP and self.dscp is None:
            raise ValueError("dscp required for DSCP policy")
        if self.policy_mode == ApplyPolicy.P_8021 and self.priority_8021p is None:
            raise ValueError("priority_8021p required for 802.1p policy")
        return self


# ---- get_cos_vlanpri / set_cos_vlanpri ---------------------------------

class CosVlanEntry(BaseModel):
    """One row of /cgi/cosvlan — VLAN-level QoS mapping."""

    vlan_id: int = Field(..., ge=1, le=4094)
    vlan_label: str
    dscp_policy: str
    priority: str


class CosVlanList(BaseModel):
    entries: list[CosVlanEntry] = Field(default_factory=list)


class SetCosVlanPriRequest(BaseModel):
    """Parameters for /cgi/cosvlanf. dscp and priority_8021p are mutually
    exclusive (the legacy UI enforces this client-side)."""

    vlan_id: int = Field(..., ge=1, le=4094)
    dscp: int = 255
    priority_8021p: int = 255

    @field_validator("dscp")
    @classmethod
    def _dscp_domain(cls, v: int) -> int:
        return _domain_or_sentinel("dscp", v, 63)

    @field_validator("priority_8021p")
    @classmethod
    def _priority_domain(cls, v: int) -> int:
        return _domain_or_sentinel("priority_8021p", v, 7)

    @model_validator(mode="after")
    def _mutually_exclusive(self) -> SetCosVlanPriRequest:
        if self.dscp != 255 and self.priority_8021p != 255:
            raise ValueError("set only one of dscp / priority_8021p at a time")
        return self


# ---- set_costos_mode ---------------------------------------------------

class SetCosTosModeRequest(BaseModel):
    mode: CosTosMode


# ---- get_dscptable / set_dscptable -------------------------------------

class DscpPolicy(BaseModel):
    """One row of /cgi/dscptable_get — DSCP → 802.1p mapping."""

    row_index: int = Field(..., ge=1, le=64)
    codepoint: str = Field(..., pattern=r"^[01]{6}$")
    priority_label: str

    @property
    def dscp(self) -> int:
        """Decode the codepoint back to its integer DSCP value (0..63)."""
        return int(self.codepoint, 2)


class DscpTable(BaseModel):
    rows: list[DscpPolicy] = Field(default_factory=list)


class SetDscpTableRequest(BaseModel):
    """Parameters for /cgi/dscptable_set. `row_index = codepoint + 1`."""

    row_index: int = Field(..., ge=1, le=64)
    priority_8021p: int

    @field_validator("priority_8021p")
    @classmethod
    def _priority_domain(cls, v: int) -> int:
        return _domain_or_sentinel("priority_8021p", v, 7)


# ---- get_diffserv / set_diffserv ---------------------------------------

class DiffservEntry(BaseModel):
    """One row of /cgi/diffserv_get — inbound DSCP policy."""

    row_index: int = Field(..., ge=1, le=64)
    inbound_codepoint: str = Field(..., pattern=r"^[01]{6}$")
    dscp_policy: str
    priority_label: str


class DiffservTable(BaseModel):
    rows: list[DiffservEntry] = Field(default_factory=list)


class SetDiffservRequest(BaseModel):
    row_index: int = Field(..., ge=1, le=64)
    dscp: int

    @field_validator("dscp")
    @classmethod
    def _dscp_domain(cls, v: int) -> int:
        return _domain_or_sentinel("dscp", v, 63)


# ---- set_cosproto ------------------------------------------------------

class SetCosProtoRequest(BaseModel):
    """Protocol-priority submit. On the 2810-24G the form is empty; exact
    field set unknown — see protocol doc (`# TODO: needs live capture`)."""

    # On this firmware the form's `<table>` body is empty; only `Apply` is
    # sent. Pinned to the legacy button caption — free text would go on the
    # wire verbatim (audit F7).
    apply: Literal["Apply Changes"] = "Apply Changes"


# ---- Response sentinels ------------------------------------------------
# Placeholder ack-only response for all write endpoints. The 2810 CGIs return
# HTML or a short `OK~...` line on success; none of the write responses are
# live-captured, so callers rely on HTTP 200 and a follow-up read.


class QosWriteAck(BaseModel):
    """HTTP-200 acknowledgement for a QoS write endpoint.

    Not derived from parsed response body — the body shape is unverified.
    """

    ok: bool = True
    raw_body: str | None = None
