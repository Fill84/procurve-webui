"""Models for the Diagnostics tab.

Sources:
- research/protocol/diagnostics/ping.md
- research/protocol/diagnostics/link_test.md
- research/protocol/diagnostics/get_configuration_report.md
- research/protocol/diagnostics/device_reset.md
"""
from __future__ import annotations

from enum import Enum, IntEnum

from pydantic import BaseModel, Field

from procurve_client.parsing import RunningConfig


class PingTestType(IntEnum):
    """Radio-button value sent as the `tp` query param."""

    PING = 1
    LINK = 2


class PingAction(str, Enum):
    START = "start"
    STOP = "stop"


class PingResult(BaseModel):
    """Parsed result of /cgi/ping (for both ping and link_test).

    The switch returns HTML containing `Successes: <N>` / `Failures: <N>`
    plus a row of LED images. Parse the two counters; preserve the raw HTML
    so the UI can render the LEDs later if desired.
    """

    successes: int = Field(..., ge=0)
    failures: int = Field(..., ge=0)
    raw_html: str


class ConfigurationReport(BaseModel):
    """Parsed /diagnostics/config.html.

    The HTML page contains the running-config verbatim inside a <pre>
    block. `raw_html` is the page as received; `config_text` is the
    <pre> contents; `running_config` is the structured parse.
    """

    raw_html: str
    config_text: str
    running_config: RunningConfig

    model_config = {"arbitrary_types_allowed": True}


class DeviceResetResponse(BaseModel):
    """Outcome of /cgi/device_reset (FORBIDDEN — see module docstring)."""

    initiated: bool = False
    message: str | None = None
