"""Status endpoints — thin wrappers around `procurve_client.operations.status`."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_transport
from procurve_client.models.log import AlertLog, DeviceStatusBanner
from procurve_client.models.port import PortCountersList, PortStatusList, PortUsageList
from procurve_client.operations.status import (
    get_alert_log,
    get_device_status,
    get_port_counters,
    get_port_status,
    get_port_usage,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/status", tags=["status"])


@router.get("/device", response_model=DeviceStatusBanner)
async def get_device_status_endpoint(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> DeviceStatusBanner:
    return await get_device_status(transport)


@router.get("/ports", response_model=PortStatusList)
async def get_port_status_endpoint(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> PortStatusList:
    return await get_port_status(transport)


@router.get("/counters", response_model=PortCountersList)
async def get_port_counters_endpoint(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> PortCountersList:
    return await get_port_counters(transport)


@router.get("/alert-log", response_model=AlertLog)
async def get_alert_log_endpoint(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> AlertLog:
    return await get_alert_log(transport)


@router.get("/port-usage", response_model=PortUsageList)
async def get_port_usage_endpoint(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008 — FastAPI pattern
) -> PortUsageList:
    """Per-port utilisation for the chassis bar chart on Status Overview.

    Returns three segments per port (``usage1``/``usage2``/``usage3`` for
    unicast-or-all-tx / non-unicast-rx / error-packets-rx respectively —
    same semantics as the legacy Java applet) plus a ``state`` letter used
    for the LED row beneath the chart.
    """
    return await get_port_usage(transport)
