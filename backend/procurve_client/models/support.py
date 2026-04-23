"""Models for the Support tab.

Source: research/protocol/support/support_redirect.md

The Support tab is a static HTML redirect to http://www.procurve.com
(defunct). No switch protocol is involved. The model exists so the new UI
can render a parity entry without calling the switch.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SupportInfo(BaseModel):
    """The static support-link info that replaces the old Support tab.

    The legacy URL is preserved for parity; `current_url` is the modern
    replacement the new UI should actually link to. `available` is False
    because the original procurve.com domain no longer resolves.
    """

    legacy_url: str = Field(
        default="http://www.procurve.com",
        description="The URL the Java applet's frameset originally loaded.",
    )
    current_url: str = Field(
        default="https://www.hpe.com/us/en/networking.html",
        description="Suggested modern replacement (HPE Networking portal).",
    )
    available: bool = Field(
        default=False,
        description="False — the legacy procurve.com URL no longer resolves.",
    )
    note: str = Field(
        default=(
            "The legacy Support tab redirected to http://www.procurve.com, "
            "which is unreachable in 2026. Use `current_url` instead."
        ),
    )
