"""Models for Configuration-tab sub-tabs that deal with network/system state.

Sources:
- research/protocol/configuration/set_ip_config.md
- research/protocol/configuration/set_default_gateway.md
- research/protocol/configuration/set_system_info.md
- research/protocol/configuration/set_fault_detection.md
- research/protocol/configuration/set_support.md
- research/protocol/configuration/set_device_features.md
- research/protocol/configuration/set_monitor.md

None of these write endpoints are live-tested; the switch returns a short
`OK~...` line or an HTML redirect. Callers rely on HTTP 200 and a follow-up
read.  Reads on these sub-tabs are HTML scrapes — see the matching
`get_<sub_tab>_page` operations.
"""
from __future__ import annotations

from enum import IntEnum
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Char whitelist used by the legacy HTML forms (system, support). Mirrors the
# JS regex at system.html:32 / support.html:39. Printable ASCII minus `~`.
SYSTEM_FIELD_PATTERN = (
    r"^[A-Za-z0-9`!@#\$%\^&\*\(\)_\+=\{\}\|\\\]\[\":;'\?><,\./ -]*$"
)
SUPPORT_FIELD_PATTERN = (
    r"^[A-Za-z0-9`!@#\$%\^&\*\(\)_\+=\{\}\|\\\]\[\":;'\?><,\./ -]+$"
)


# ---- IP config ---------------------------------------------------------

class IpMode(IntEnum):
    DISABLED = 1
    MANUAL = 2
    DHCP = 3


class IpConfigPage(BaseModel):
    """Scraped state from /configuration/ip1.html + /configuration/ip2.html.

    `ip_address` / `subnet_mask` are injected plain-text on ip2.html and are
    read-only on this firmware — they are not editable via the web UI.
    """

    vlan_id: int = Field(..., ge=1, le=4094)
    mode: IpMode
    ip_address: IPv4Address | None = None
    subnet_mask: str | None = None
    gateway: IPv4Address


class SetIpConfigRequest(BaseModel):
    gateway: IPv4Address
    vlan_id: int = Field(..., ge=1, le=4094)
    mode: IpMode


class SetDefaultGatewayRequest(BaseModel):
    gateway: IPv4Address


# ---- System info -------------------------------------------------------

class SystemInfoPage(BaseModel):
    """Scraped state from /configuration/system.html."""

    mac_address: str = Field(
        ..., pattern=r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$"
    )
    name: str
    location: str
    contact: str


class SetSystemInfoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, pattern=SYSTEM_FIELD_PATTERN)
    location: str = Field("", max_length=48, pattern=SYSTEM_FIELD_PATTERN)
    contact: str = Field("", max_length=48, pattern=SYSTEM_FIELD_PATTERN)


# ---- Fault detection ---------------------------------------------------

class FaultSensitivity(IntEnum):
    NEVER = 0
    HIGH = 32
    MEDIUM = 128
    LOW = 224


class FaultDetectionPage(BaseModel):
    """Scraped state from /configuration/web_agent.html."""

    sensitivity: FaultSensitivity
    # `dps` is a second injected variable (read-only telemetry). Preserved
    # verbatim — purpose undocumented.
    dps: int | None = None


class SetFaultDetectionRequest(BaseModel):
    sensitivity: FaultSensitivity


# ---- Support URLs ------------------------------------------------------

class SupportPage(BaseModel):
    """Scraped state from /configuration/support.html."""

    support_url: str
    mgmt_url: str


class SetSupportRequest(BaseModel):
    support_url: str = Field(
        ..., min_length=1, max_length=103, pattern=SUPPORT_FIELD_PATTERN
    )
    mgmt_url: str = Field(
        ..., min_length=1, max_length=103, pattern=SUPPORT_FIELD_PATTERN
    )


# ---- Device features (IGMP / STP) --------------------------------------

class FeatureEndpoint(str):
    """Enum-style marker for the switch-side feature endpoint path.

    Five wire paths exist across firmware variants — see protocol doc.
    """

    # These are plain string constants rather than an Enum to keep the
    # transport.get() call site simple.
    SINGLE_VLAN = "/cgi/feature_set"
    SINGLE_VLAN_CRIP = "/cgi/feature2_set"
    MULTI_VLAN_GLOBAL = "/cgi/globalfeature_set"
    MULTI_VLAN_PER_VLAN = "/cgi/vlanfeature_set"
    MULTI_VLAN_PER_VLAN_CRIP = "/cgi/vlan2feature_set"


class DeviceFeaturesPage(BaseModel):
    """Scraped state from /configuration/features2*.html.

    `igmp` and `spanning_tree` are `None` when the injected JS variable was
    `Invalid OID` (page-generator quirk on multi-VLAN variants).
    """

    vlan_count: int = Field(..., ge=1)
    crip_stat: str = "0"
    igmp: bool | None = None
    spanning_tree: bool | None = None


class SetDeviceFeaturesRequest(BaseModel):
    """Write request for one of the five feature-set endpoints.

    Use `endpoint` to pick the correct wire path. Each legacy page submits
    a fixed field set (mirror pages features2/2a/2b/2c/2d), so the model
    enforces exactly that combination — the applet could never emit
    anything else (audit F5):

    * ``feature_set`` / ``feature2_set`` — IGMP **and** Spanning Tree
    * ``globalfeature_set`` — Spanning Tree only
    * ``vlanfeature_set`` / ``vlan2feature_set`` — IGMP only
    """

    endpoint: Literal[
        "/cgi/feature_set",
        "/cgi/feature2_set",
        "/cgi/globalfeature_set",
        "/cgi/vlanfeature_set",
        "/cgi/vlan2feature_set",
    ] = "/cgi/feature_set"
    vlan_id: int = Field(default=1, ge=1, le=4094)
    igmp: bool | None = None
    spanning_tree: bool | None = None

    @model_validator(mode="after")
    def _fields_match_endpoint(self) -> SetDeviceFeaturesRequest:
        wants_igmp = self.endpoint != "/cgi/globalfeature_set"
        wants_stp = self.endpoint in ("/cgi/feature_set", "/cgi/feature2_set",
                                      "/cgi/globalfeature_set")
        if wants_igmp and self.igmp is None:
            raise ValueError(f"{self.endpoint} requires igmp")
        if not wants_igmp and self.igmp is not None:
            raise ValueError(f"{self.endpoint} has no IGMP select")
        if wants_stp and self.spanning_tree is None:
            raise ValueError(f"{self.endpoint} requires spanning_tree")
        if not wants_stp and self.spanning_tree is not None:
            raise ValueError(f"{self.endpoint} has no Spanning Tree select")
        return self


# ---- Monitor (port mirroring) ------------------------------------------

class MonitorPage(BaseModel):
    """Scraped state from /configuration/monitor1.html."""

    enabled: bool
    # Candidate destination ports advertised by the <Select monitoringPort>
    # (some ports are excluded by the switch, e.g. trunk members).
    candidate_dest_ports: list[int] = Field(default_factory=list)
    selected_dest_port: int | None = None


class SetMonitorRequest(BaseModel):
    """Port-mirroring write. Source ports are 1-based port numbers.

    The wire encoding of `portCopySourceMask` (space-separated hex byte
    pairs, port 1 = MSB — MonitorList.java:getPortMask) is produced by
    `operations.configuration.monitor_source_mask`, not stored here.
    The 1..32 bound matches the applet's single-32-bit-word mask on this
    device (2810-24G tops out at port 24).
    """

    enabled: bool
    dest_port: int | None = Field(default=None, ge=1, le=32)
    source_ports: list[int] | None = None

    @field_validator("source_ports")
    @classmethod
    def _ports_in_range(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and any(p < 1 or p > 32 for p in v):
            raise ValueError("source_ports must be within 1..32")
        return v

    @model_validator(mode="after")
    def _requires(self) -> SetMonitorRequest:
        if self.enabled and (self.dest_port is None or not self.source_ports):
            raise ValueError(
                "enabling monitoring requires dest_port and a non-empty source_ports"
            )
        return self


# ---- Generic ack -------------------------------------------------------

class ConfigWriteAck(BaseModel):
    """Shared ack type for write endpoints whose response body is unverified."""

    ok: bool = True
    raw_body: str | None = None
