"""Support endpoint — returns static parity info for the legacy Support tab.

The legacy Support tab was a static HTML redirect to http://www.procurve.com
(defunct). `support_redirect` is a pure-info operation that takes no transport,
so this endpoint does no switch I/O — it only requires a valid session for
consistency with the rest of the API.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import SessionEntry
from app.deps import get_session
from procurve_client.models.support import SupportInfo
from procurve_client.operations.support import support_redirect

router = APIRouter(prefix="/api/v1/support", tags=["support"])


@router.get("", response_model=SupportInfo)
async def get_support(
    _: SessionEntry = Depends(get_session),  # noqa: B008 — FastAPI pattern
) -> SupportInfo:
    """Return the static Support-tab info. No switch I/O."""
    return await support_redirect()
