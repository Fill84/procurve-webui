"""Models for port status, counters, usage, and configuration.

Sources:
- research/protocol/status/get_port_status.md
- research/protocol/status/get_port_counters.md
- research/protocol/status/get_port_usage.md
- research/protocol/configuration/get_portscfg.md
- research/protocol/configuration/get_port_form.md
- research/protocol/configuration/set_port_config.md
- research/protocol/configuration/get_bobports.md
- research/protocol/configuration/set_bobports.md
"""
from __future__ import annotations

from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PortStatus(BaseModel):
    """One row from /cgi/get_ports.

    Wire has 10 fields but the GUI only renders 8 columns. Wire position 2
    is a hidden decorative label (single space for most ports; e.g. "UPS" on
    a labelled port) — preserved as `port_type_label`. Wire position 9 is a
    trailing integer always observed as `0` — preserved as `_extra` for
    round-trip fidelity; its purpose is unknown.
    """

    port: int = Field(..., ge=1)
    port_name: str
    port_type_label: str = ""
    port_type: str
    enabled: bool
    link_status: Literal["Up", "Down"]
    current_mode: str
    trunk: str = ""
    flow_ctrl: str
    # Wire position 9 — always 0 in observed captures; purpose unknown.
    # TODO: needs live capture under alternate port conditions to confirm shape.
    extra: int = Field(0, ge=0, description="Unknown trailing integer; observed 0.")


class PortStatusList(BaseModel):
    ports: list[PortStatus]


class PortCounters(BaseModel):
    """One row from /cgi/portc.

    Wire position 2 is the same hidden label cell shared with /cgi/get_ports
    (preserved as `port_type_label`). Counters are packet counts, not bytes,
    and wrap at 2^32 — callers computing deltas must tolerate wrap.
    """

    port: int = Field(..., ge=1)
    port_name: str
    port_type_label: str = ""
    mcast_rx: int = Field(..., ge=0)
    mcast_tx: int = Field(..., ge=0)
    bcast_rx: int = Field(..., ge=0)
    bcast_tx: int = Field(..., ge=0)
    pkts_rx: int = Field(..., ge=0)
    pkts_tx: int = Field(..., ge=0)
    errors_rx: int = Field(..., ge=0)


class PortCountersList(BaseModel):
    ports: list[PortCounters]


class PortUsage(BaseModel):
    """One row from /cgi/port_usage.

    Three `usage*` slots are segments of a stacked bar the applet renders;
    their individual semantics are not documented by HP. Callers can sum
    them via `total_usage_pct` for overall utilisation percent.
    """

    port: int = Field(..., ge=1)
    label: str
    state: Literal["G", "W", "N", "R"]
    usage1: int = Field(..., ge=0, le=100)
    usage2: int = Field(..., ge=0, le=100)
    usage3: int = Field(..., ge=0, le=100)
    speed: str | None = None

    @property
    def total_usage_pct(self) -> int:
        return self.usage1 + self.usage2 + self.usage3


class PortUsageList(BaseModel):
    ports: list[PortUsage]


# ---- Configuration-tab: get_portscfg -----------------------------------

class PortConfig(BaseModel):
    """One row from /cgi/get_portscfg (the Configuration tab's Ports list).

    Structurally near-identical to `PortStatus` but semantically different:
    position 5 is `config_status` (`.` = nothing to report) and position 6
    is the *configured* mode, not the current negotiated one.
    """

    port: int = Field(..., ge=1)
    port_name: str
    port_type_label: str = ""
    port_type: str
    enabled: bool
    config_status: str
    config_mode: str
    trunk: str = ""
    flow_control: bool
    extra: int = Field(0, ge=0, description="Wire position 9; observed 0. Unknown.")


class PortConfigList(BaseModel):
    ports: list[PortConfig]


# ---- Configuration-tab: get_port_form / set_port_config -----------------

class PortMode(IntEnum):
    """Values from the <select name=hpSwitchPortFastEtherMode> on port_form.

    Value `6` is unused (a legacy auto mode removed in this firmware).
    """

    HDX_10 = 1
    HDX_100 = 2
    FDX_10 = 3
    FDX_100 = 4
    AUTO = 5
    AUTO_10 = 7
    AUTO_100 = 8
    AUTO_1000 = 9
    AUTO_10_100 = 11


class PortForm(BaseModel):
    """Parsed result of /cgi/port_form?indeces=... — the per-port edit form.

    `port_name` may be `""` when a single port is selected and has no name;
    on multi-port selects where ports disagree it is empty too (the live UI
    would render it as "differs across selection").
    """

    ports: list[int]
    port_name: str = ""
    admin_enabled: bool
    mode: PortMode
    flow_control_enabled: bool


class SetPortConfigRequest(BaseModel):
    """Parameters for /cgi/mod_ports."""

    ports: list[int] = Field(..., min_length=1)
    name: str = Field(default="", max_length=64)
    admin_enabled: bool = True
    mode: PortMode = PortMode.AUTO_1000
    flow_control_enabled: bool = True

    @field_validator("ports")
    @classmethod
    def _positive(cls, v: list[int]) -> list[int]:
        if any(p < 1 for p in v):
            raise ValueError("ports must be >= 1")
        return v

    @field_validator("name")
    @classmethod
    def _no_tilde(cls, v: str) -> str:
        if "~" in v:
            raise ValueError("port name must not contain '~'")
        return v

    @model_validator(mode="after")
    def _flow_duplex_match(self) -> SetPortConfigRequest:
        # Client-side rule from chkSubmit(): flow control cannot be on for
        # half-duplex modes.
        if self.flow_control_enabled and self.mode in (PortMode.HDX_10, PortMode.HDX_100):
            raise ValueError(
                "flow_control_enabled=True is not allowed with half-duplex modes"
            )
        return self


# ---- Device View (bobports) --------------------------------------------

class BobDevice(BaseModel):
    """First line of /cgi/get_bobports — switch chassis metadata."""

    codename: str
    port_count: int = Field(..., ge=1)


class BobPort(BaseModel):
    """One port line from /cgi/get_bobports.

    `label` is the rendered label the applet shows under the port — it may
    differ from the SNMP port name. `mode` and `poe` are optional (many
    firmwares omit the trailing fields).
    """

    port: int = Field(..., ge=1)
    kind: str
    label: str = ""
    link: bool
    enabled: bool
    mode: str | None = None
    poe: int | None = None


class BobPortsResponse(BaseModel):
    """Device + port rollup for /cgi/get_bobports."""

    device: BobDevice
    ports: list[BobPort] = Field(default_factory=list)


class SetBobPortsRequest(BaseModel):
    """Parameters for /cgi/set_bobports (the bulk enable/disable button).

    Wire uses `ifAdminStatus=1` for enable, `=2` for disable; port list goes
    into `indeces=<csv>` (note the misspelling — preserved on the wire).
    """

    enable: bool
    ports: list[int] = Field(..., min_length=1)

    @field_validator("ports")
    @classmethod
    def _positive(cls, v: list[int]) -> list[int]:
        if any(p < 1 for p in v):
            raise ValueError("ports must be >= 1")
        return v
