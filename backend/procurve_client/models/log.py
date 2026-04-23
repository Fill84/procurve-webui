"""Models for switch alert log / device status banner (Status tab).

Sources:
- research/protocol/status/get_alert_log.md
- research/protocol/status/get_device_status.md
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
