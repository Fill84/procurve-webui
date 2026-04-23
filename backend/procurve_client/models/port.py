"""Models for port status, counters, and usage (Status tab).

Sources:
- research/protocol/status/get_port_status.md
- research/protocol/status/get_port_counters.md
- research/protocol/status/get_port_usage.md
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
