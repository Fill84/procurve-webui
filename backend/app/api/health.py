"""Health endpoint — unauthenticated liveness probe against the switch.

Intentionally does NOT use `get_transport` (no session required). This is a
lightweight probe for monitoring: it opens a one-shot `ProcurveTransport`
with `NoneAuth()` and hits `/home.html`. On any failure it returns HTTP 503
with `{status: "unreachable", switch_reachable: false}`.
"""
from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.settings import Settings
from procurve_client.auth import NoneAuth
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok", "unreachable"]
    switch_reachable: bool


@router.get("", response_model=HealthStatus)
async def get_health(request: Request, response: Response) -> HealthStatus:
    settings = cast(Settings, request.app.state.settings)
    transport = ProcurveTransport(
        host=settings.switch_host,
        port=settings.switch_port,
        auth=NoneAuth(),
    )
    try:
        async with transport:
            r = await transport.get("/home.html")
    except Exception:  # noqa: BLE001 — any failure maps to "unreachable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unreachable", switch_reachable=False)

    if r.status_code != 200:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unreachable", switch_reachable=False)
    return HealthStatus(status="ok", switch_reachable=True)
