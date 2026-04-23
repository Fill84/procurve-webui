"""Models for the Configuration → VLAN subsystem.

Sources:
- research/protocol/configuration/vlan/*.md (15 ops)

Wire conventions (see research/protocol/configuration/vlan/_conventions.md):
- Reads:
  - `getVLANMode` / `getGVRPMode` return a bare `ON\\n` or `OFF\\n` line.
  - `getVLANAll` is a multi-line stream; each line is tilde-delimited.
  - `listVLANS` is a single tilde-delimited stream of `(id, name)` pairs.
  - `getVLANPort` / `getGVRPPort` lead with an `ON`/`OFF` sentinel followed
    by `(port_name, port_id, mode)` triples.
  - `getVLANProtocol` is a bare tilde stream of protocol names; empty body
    is a legitimate "no protocols assigned" response.
- Writes: `addVLAN`, `delVLAN`, `renVLAN`, `setVLANPort`, `setGVRPPort`,
  `setVLANMode`, `setGVRPMode`, `setPrimary` all speak the `OK~...` /
  `error~...` sentinel shape or a bare `OK`.
- Mode integer encodings differ per subsystem:
  - VLAN port mode: 0=Auto/No, 1=Tagged, 2=Untagged, 3=Forbid
  - GVRP port mode: 0=Disable, 1=Learn, 2=Block
  - setVLANMode / setGVRPMode: 1=enable, 2=disable (NOT 0/1)
"""
from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel, Field, field_validator

# ---- Port-mode enums ----------------------------------------------------


class VlanPortMode(IntEnum):
    """Per-port VLAN membership mode (getVLANPort / setVLANPort).

    `AUTO` is labelled "Auto" when GVRP is ON and "No" when GVRP is OFF,
    but the integer value is the same either way.
    """

    AUTO = 0
    TAGGED = 1
    UNTAGGED = 2
    FORBID = 3


class GvrpPortMode(IntEnum):
    """Per-port GVRP mode (getGVRPPort / setGVRPPort)."""

    DISABLE = 0
    LEARN = 1
    BLOCK = 2


# ---- VLAN summary & full records ---------------------------------------


class Vlan(BaseModel):
    """A single VLAN as reported by `getVLANAll` (family=1 fields).

    Port-list fields are preserved as raw wire strings. The applet converts
    `|` to `,` only for display; the raw wire uses `|` between ranges (or
    `,` — seen in the fixture because of trailing Dyn-range rendering).
    The literal `None` string means "empty list".
    """

    vlan_id: int = Field(..., ge=1, le=4094)
    vlan_name: str
    vlan_type: str  # STATIC | DYNAMIC
    tagged_ports: str
    gvrp_ports: str
    untagged_ports: str
    forbid_ports: str
    auto_ports: str


class VlanList(BaseModel):
    """Parsed shape of `/cgi/getVLANAll`."""

    vlans: list[Vlan]


class VlanSummary(BaseModel):
    """A `(id, name)` pair as reported by `listVLANS`."""

    vlan_id: int = Field(..., ge=1, le=4094)
    vlan_name: str


class VlanSummaryList(BaseModel):
    """Parsed shape of `/cgi/listVLANS`."""

    vlans: list[VlanSummary]


# ---- Mode flags --------------------------------------------------------


class VlanModeFlag(BaseModel):
    """Shared shape for `getVLANMode` and `getGVRPMode`."""

    enabled: bool  # True when wire was "ON"


# ---- GVRP per-port state ----------------------------------------------


class GvrpPort(BaseModel):
    """One row of `getGVRPPort`.

    When GVRP is globally OFF the firmware leaves the mode column of
    non-trunk ports uninitialised (observed `-2141579148`); such rows have
    `mode=None` in our parsed model.
    """

    port_name: str
    port_id: int
    mode: GvrpPortMode | None = None


class GvrpPortList(BaseModel):
    """Parsed shape of `/cgi/getGVRPPort`.

    `gvrp_enable` is the leading `ON`/`OFF` sentinel; when False, callers
    should treat `ports[*].mode` as stale per the applet's own behaviour.
    """

    gvrp_enable: bool
    ports: list[GvrpPort]


# ---- VLAN per-port membership -----------------------------------------


class VlanMembership(BaseModel):
    """One row of `getVLANPort` — the mode a port is in for one VLAN."""

    port_name: str
    port_id: int
    mode: VlanPortMode


class VlanMembershipList(BaseModel):
    """Parsed shape of `/cgi/getVLANPort?VLAN_ID=<id>`."""

    vlan_id: int
    gvrp_enable: bool
    ports: list[VlanMembership]


# ---- Protocol-VLAN list -----------------------------------------------


class VlanProtocolList(BaseModel):
    """Parsed shape of `/cgi/getVLANProtocol?VLAN_ID=<id>`.

    Empty body is a valid result on family=1 switches that don't expose
    protocol VLANs (e.g. our 2810).
    """

    vlan_id: int
    protocols: list[str]


# ---- Write requests ----------------------------------------------------


def _no_tilde_no_space(v: str) -> str:
    if "~" in v:
        raise ValueError("VLAN name cannot contain '~'")
    if " " in v:
        raise ValueError("VLAN name cannot contain spaces")
    return v


class AddVlanRequest(BaseModel):
    """Arguments for `/cgi/addVLAN`."""

    vlan_id: int = Field(..., ge=1, le=4094)
    vlan_name: str = Field(..., min_length=1, max_length=12)

    @field_validator("vlan_name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _no_tilde_no_space(v)


class DelVlanRequest(BaseModel):
    """Arguments for `/cgi/delVLAN` (duplicate-key VLAN_ID)."""

    vlan_ids: list[int] = Field(..., min_length=1)

    @field_validator("vlan_ids")
    @classmethod
    def _validate_range(cls, v: list[int]) -> list[int]:
        for i in v:
            if not (1 <= i <= 4094):
                raise ValueError(f"vlan_id {i} out of range 1..4094")
        return v


class RenVlanRequest(BaseModel):
    """Arguments for `/cgi/renVLAN`."""

    vlan_id: int = Field(..., ge=1, le=4094)
    vlan_name: str = Field(..., min_length=1, max_length=12)

    @field_validator("vlan_name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _no_tilde_no_space(v)


class SetPrimaryVlanRequest(BaseModel):
    """Arguments for `/cgi/setPrimary`."""

    vlan_id: int = Field(..., ge=1, le=4094)


class PortModeChange(BaseModel):
    """One (port_id, mode) pair for set{VLAN,GVRP}Port requests."""

    port_id: int = Field(..., ge=1)
    mode: int = Field(..., ge=0, le=3)


class SetVlanPortsRequest(BaseModel):
    """Arguments for `/cgi/setVLANPort`.

    `changes` is an ordered list — the wire interleaves PORT/MODE pairs in
    this order. Only ports whose mode actually changed should appear; the
    applet calls `getChangedPortsID()` and the switch may reject
    unnecessary updates.
    """

    vlan_id: int = Field(..., ge=1, le=4094)
    changes: list[PortModeChange] = Field(..., min_length=1)

    @field_validator("changes")
    @classmethod
    def _validate_modes(cls, v: list[PortModeChange]) -> list[PortModeChange]:
        for c in v:
            if c.mode not in (0, 1, 2, 3):
                raise ValueError(f"VLAN port mode {c.mode} not in 0..3")
        return v


class SetGvrpPortsRequest(BaseModel):
    """Arguments for `/cgi/setGVRPPort` (no VLAN_ID prefix)."""

    changes: list[PortModeChange] = Field(..., min_length=1)

    @field_validator("changes")
    @classmethod
    def _validate_modes(cls, v: list[PortModeChange]) -> list[PortModeChange]:
        for c in v:
            if c.mode not in (0, 1, 2):
                raise ValueError(f"GVRP port mode {c.mode} not in 0..2")
        return v


class SetVlanModeRequest(BaseModel):
    """Arguments for `/cgi/setVLANMode` (requires reboot)."""

    enabled: bool

    def to_wire_mode(self) -> int:
        return 1 if self.enabled else 2


class SetGvrpModeRequest(BaseModel):
    """Arguments for `/cgi/setGVRPMode`."""

    enabled: bool

    def to_wire_mode(self) -> int:
        return 1 if self.enabled else 2


# ---- Write acks --------------------------------------------------------


class VlanWriteAck(BaseModel):
    """Return shape for VLAN-subsystem write endpoints.

    Most write CGIs emit `OK~<listVLANS refresh>` on success or an error
    string on failure. The refresh payload is exposed as `vlans` when
    present so the caller can avoid a follow-up round-trip.
    """

    ok: bool = True
    raw_body: str | None = None
    vlans: list[VlanSummary] = Field(default_factory=list)
