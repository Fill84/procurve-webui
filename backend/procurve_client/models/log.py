"""Models for switch alert log / device status banner (Status tab).

Sources:
- research/protocol/status/get_alert_log.md
- research/protocol/status/get_device_status.md
- research/protocol/status/get_alert_detail.md
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AlertEvent(BaseModel):
    """One row from the alert-log stream (/cgi/fflog?action=list)."""

    row_id: str
    alert_name: str
    category: str
    ts_centiseconds: int = Field(..., ge=0)
    description: str


class AlertLog(BaseModel):
    """Parsed /cgi/fflog?action=list response.

    Line 1 is a meta/cursor line; subsequent lines are alert rows.
    """

    latest_ts_centiseconds: int = Field(..., ge=0)
    cursor_or_count: int = Field(..., ge=0)
    events: list[AlertEvent]


class DeviceStatusBanner(BaseModel):
    """Parsed /cgi/fflog?action=status response (first line only).

    The applet reads exactly one line and tokenizes on `~` (positions 0..3).
    On this firmware the response body is identical to action=list, but the
    first line is a 2-field meta record — the applet ignores trailing lines.
    """

    state: str
    index: str | None = None
    description: str | None = None
    ts_centiseconds: int | None = Field(None, ge=0)


class AlertDetail(BaseModel):
    """Structured view of GET /cgi/ffdetail?index=<N>&dt=<ts>.

    Source: research/protocol/status/get_alert_detail.md.
    The wire is HTML; we extract title / hdr() args / ffbuttons setTimeout
    discriminators / description-solution-other-possibilities sections.
    Optional fields are ``None`` / empty list when missing — alert types
    differ in which sections they include.
    """

    index: int
    ts_centiseconds: int = Field(..., ge=0)
    title: str
    severity: int = Field(..., ge=1, le=5)
    affected_port: int = Field(..., ge=0)
    type_code: int = Field(..., ge=0)
    act_code: int = Field(..., ge=0)
    description: str | None = None
    solution: list[str] = Field(default_factory=list)
    other_possibilities: str | None = None
    raw_html: str
