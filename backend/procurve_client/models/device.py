"""Models for switch device identity (Identity tab).

Source: research/protocol/identity/read_identity_page.md

The Identity tab is a server-rendered HTML page with no CGI; values are
interpolated into JavaScript string literals which are then emitted via
document.write(). Parsing uses regex over the raw HTML body.
"""
from __future__ import annotations

from ipaddress import IPv4Address

from pydantic import BaseModel, Field


class DeviceIdentity(BaseModel):
    """Parsed switch identity as rendered by /identity/identity.html.

    All trailing whitespace the template emits in cells is stripped on parse.
    The `management_server_url` is `None` when the switch has no URL
    configured (the applet helper `link("")` renders "(None)" in that case).
    """

    system_name: str = Field(..., description="Hostname (identity.html:86).")
    system_location: str = Field(..., description="SNMP sysLocation.")
    system_contact: str = Field(..., description="SNMP sysContact.")
    uptime_centiseconds: int = Field(
        ..., ge=0, description="Hundredths of a second since boot; ft() divides by 100."
    )
    cpu_pct: int = Field(..., ge=0, le=100, description="System CPU utilisation %.")
    memory_total_bytes: int = Field(..., ge=0, description="Total system memory (bytes).")
    memory_free_bytes: int = Field(..., ge=0, description="Free system memory (bytes).")
    product: str = Field(..., description="e.g. 'ProCurve Switch 2810-24G (J9021A)'.")
    base_mac: str = Field(
        ...,
        pattern=r"^[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}$",
        description="Base MAC in canonical colon-separated uppercase.",
    )
    serial_number: str = Field(..., description="Switch serial number.")
    firmware_version: str = Field(..., description="e.g. 'N.11.78, ROM N.10.01'.")
    ip_address: IPv4Address = Field(..., description="Management IPv4.")
    management_server_url: str | None = Field(
        None, description="URL rendered by link(); None when switch reports '(None)'."
    )
