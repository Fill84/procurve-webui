"""Identity endpoint — thin wrapper around `read_identity_page`."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_transport
from procurve_client.models.device import DeviceIdentity
from procurve_client.operations.identity import read_identity_page
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


@router.get("", response_model=DeviceIdentity)
async def get_identity(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> DeviceIdentity:
    return await read_identity_page(transport)
