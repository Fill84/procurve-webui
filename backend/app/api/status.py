"""Status endpoints — thin wrappers around `procurve_client.operations.status`.

Reads (5):
  GET  /api/v1/status/device              -> DeviceStatusBanner
  GET  /api/v1/status/ports               -> PortStatusList
  GET  /api/v1/status/counters            -> PortCountersList
  GET  /api/v1/status/alert-log           -> AlertLog
  GET  /api/v1/status/port-usage          -> PortUsageList
  GET  /api/v1/status/alerts/{index}?dt=  -> AlertDetail

Writes (2 — fault-log mutations, gated by READ_ONLY but NO auto-backup):
  POST /api/v1/status/alerts/ack          -> ConfigWriteAck
  POST /api/v1/status/alerts/delete       -> ConfigWriteAck

Write-safety policy
-------------------
``ack_alerts`` / ``delete_alerts`` mutate only the in-memory fault-log on
the switch — they do NOT modify running-config. They follow the same
exception we made for ping/link-test in the Diagnostics tab:

* gated by :func:`require_writable` so ``READ_ONLY=true`` blocks them,
* but NOT wrapped in :func:`write_with_autobackup`. The backed-up config
  doesn't include the fault log, so a pre-write snapshot would be wasted
  I/O and provide no rollback value.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import get_app_settings, get_transport
from app.settings import Settings
from app.write_safety import require_writable
from procurve_client.models.log import (
    AlertDetail,
    AlertEvent,
    AlertLog,
    DeviceStatusBanner,
)
from procurve_client.models.network import ConfigWriteAck
from procurve_client.models.port import PortCountersList, PortStatusList, PortUsageList
from procurve_client.operations.status import (
    ack_alerts,
    delete_alerts,
    get_alert_detail,
    get_alert_log,
    get_device_status,
    get_port_counters,
    get_port_status,
    get_port_usage,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/status", tags=["status"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class AlertEventRef(BaseModel):
    """Minimal client-supplied identifier for an event we want to act on.

    Only `row_id` and `ts_centiseconds` are required on the wire (see
    research/protocol/status/ack_alerts.md). The full :class:`AlertEvent`
    model carries `alert_name`/`category`/`description` too, but those are
    not part of the ack/del query string. The endpoint adapts this minimal
    shape into a full ``AlertEvent`` (with empty filler strings for the
    unused fields) before delegating to the procurve_client op.
    """

    row_id: str
    ts_centiseconds: int = Field(..., ge=0)


class AckAlertsBody(BaseModel):
    """Body for POST /api/v1/status/alerts/ack and /alerts/delete."""

    events: list[AlertEventRef] = Field(..., min_length=1)


def _refs_to_events(refs: list[AlertEventRef]) -> list[AlertEvent]:
    """Pad each AlertEventRef out to a full AlertEvent.

    The procurve_client op signature is ``events: list[AlertEvent]`` — only
    the row_id and ts_centiseconds are read from each event. We supply
    empty strings for the unused fields rather than refactor the op
    signature, since the op will likely keep the full type for symmetry
    with `get_alert_log` returning `AlertEvent` instances.
    """
    return [
        AlertEvent(
            row_id=ref.row_id,
            alert_name="",
            category="",
            ts_centiseconds=ref.ts_centiseconds,
            description="",
        )
        for ref in refs
    ]


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


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


@router.get("/alerts/{index}", response_model=AlertDetail)
async def get_alert_detail_endpoint(
    index: int,
    dt: int,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> AlertDetail:
    """Fetch the parsed detail page for a single alert event.

    The `dt` query param doubles as an integrity token on the switch — pass
    the `ts_centiseconds` of the event row from the alert-log response.
    """
    return await get_alert_detail(transport, index=index, ts_centiseconds=dt)


# ---------------------------------------------------------------------------
# Fault-log writes (READ_ONLY-gated, NO auto-backup — see module docstring)
# ---------------------------------------------------------------------------


@router.post("/alerts/ack", response_model=ConfigWriteAck)
async def ack_alerts_endpoint(
    body: AckAlertsBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> ConfigWriteAck:
    """Acknowledge one or more events in the switch fault log.

    Mirrors the diagnostics ping/link-test exception: gated by
    :func:`require_writable` but **NOT** wrapped in
    :func:`write_with_autobackup`. The fault log is RAM-only state; there
    is nothing in running-config to back up before the call.
    """
    require_writable(settings)
    return await ack_alerts(transport, events=_refs_to_events(body.events))


@router.post("/alerts/delete", response_model=ConfigWriteAck)
async def delete_alerts_endpoint(
    body: AckAlertsBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> ConfigWriteAck:
    """Delete one or more events from the switch fault log.

    Same write-safety policy as ack — read-only-gated, no auto-backup.
    The UI must wrap this with a `window.confirm` (or modal) before firing,
    matching the legacy applet's `confirm("Are you sure...")` prompt.
    """
    require_writable(settings)
    return await delete_alerts(transport, events=_refs_to_events(body.events))
