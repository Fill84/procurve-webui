"""Support-tab operations.

Contract from Phase 0: research/protocol/support/support_redirect.md

The Support tab of the legacy 2810 UI is a pure static HTML redirect to
`http://www.procurve.com` (defunct). There is no CGI and no switch state
to read; this function returns a `SupportInfo` model so the new UI can
render a parity entry without calling the switch.
"""
from __future__ import annotations

from procurve_client._safety import READ
from procurve_client.models.support import SupportInfo


@READ
async def support_redirect() -> SupportInfo:
    """Return the static Support-tab info (legacy URL + modern replacement).

    Intentionally takes no transport — no switch call is needed.
    """
    return SupportInfo()
