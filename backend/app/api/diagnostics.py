"""Diagnostics API (Task 3.3): ping, link test, configuration report, device reset.

Endpoints:
  POST /api/v1/diagnostics/ping                  — ICMP probe (gated by READ_ONLY)
  POST /api/v1/diagnostics/link-test             — L2 link test  (gated by READ_ONLY)
  GET  /api/v1/diagnostics/configuration-report  — scraped running-config text
  POST /api/v1/diagnostics/device-reset          — DANGEROUS: reboot the switch

Write-safety policy
-------------------
``ping`` and ``link_test`` are decorated ``@WRITE`` in
``procurve_client.operations.diagnostics`` because they cause the switch to
emit ICMP/link-test packets. They do *not* mutate persistent switch state,
so the Phase 3 policy for these two endpoints is:

  * gate behind :func:`require_writable(settings)` so ``READ_ONLY=true``
    disables diagnostic traffic (matches the HP applet where read-only users
    cannot send test packets),
  * but DO NOT wrap in :func:`write_with_autobackup`. There is nothing to
    back up — no config changes, so taking a pre-write snapshot would be
    busy-work and would slow every ping by a full config download.

``device-reset`` reboots the switch. This is the full safety pattern:
``require_writable`` + :func:`require_host_confirmation` (the caller must type
the switch IP into ``confirm_switch_host``) + :func:`write_with_autobackup`
so the operator still has a rollback point after the box comes back up.

Tests never invoke ``device_reset`` against a real switch. The code exists
for protocol parity only; every test in this module mocks the operation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.backup_store import BackupStore
from app.deps import get_app_settings, get_backup_store, get_transport
from app.settings import Settings
from app.write_safety import (
    require_host_confirmation,
    require_writable,
    write_with_autobackup,
)
from procurve_client.models.diagnostics import (
    DeviceResetResponse,
    PingResult,
)
from procurve_client.operations.diagnostics import (
    device_reset,
    get_configuration_report,
    link_test,
    ping,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


# ---------------------------------------------------------------------------
# Request/response bodies
# ---------------------------------------------------------------------------


class PingRequest(BaseModel):
    """Ping test. `destination` is an IPv4 address or hostname."""

    destination: str
    packet_count: int = 10
    timeout_s: int = 5


class LinkTestRequest(BaseModel):
    """L2 link test. `destination` is a MAC address (dash- or colon-separated)."""

    destination: str
    packet_count: int = 10
    timeout_s: int = 5


class DeviceResetRequest(BaseModel):
    """Reboot confirmation. `confirm_switch_host` must equal settings.switch_host."""

    confirm_switch_host: str


class ConfigurationReportResponse(BaseModel):
    """Trimmed view of :class:`procurve_client.models.diagnostics.ConfigurationReport`.

    The full model carries a ``running_config`` dataclass for the structured
    parse; the Diagnostics tab only needs the rendered text + raw HTML, so we
    return a flat Pydantic model here to keep the OpenAPI schema clean.
    """

    raw_html: str
    config_text: str


# ---------------------------------------------------------------------------
# Ping / Link test (gated by READ_ONLY, NOT auto-backed up — see module docstring)
# ---------------------------------------------------------------------------


@router.post("/ping", response_model=PingResult)
async def run_ping(
    body: PingRequest,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> PingResult:
    require_writable(settings)
    return await ping(
        transport,
        destination=body.destination,
        packet_count=body.packet_count,
        timeout_s=body.timeout_s,
    )


@router.post("/link-test", response_model=PingResult)
async def run_link_test(
    body: LinkTestRequest,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
) -> PingResult:
    require_writable(settings)
    return await link_test(
        transport,
        destination=body.destination,
        packet_count=body.packet_count,
        timeout_s=body.timeout_s,
    )


# ---------------------------------------------------------------------------
# Configuration report (read-only — no gate, no backup)
# ---------------------------------------------------------------------------


@router.get("/configuration-report", response_model=ConfigurationReportResponse)
async def configuration_report(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> ConfigurationReportResponse:
    report = await get_configuration_report(transport)
    return ConfigurationReportResponse(
        raw_html=report.raw_html,
        config_text=report.config_text,
    )


# ---------------------------------------------------------------------------
# Device reset (FULL safety: require_writable + host-confirm + autobackup)
# ---------------------------------------------------------------------------


@router.post("/device-reset", response_model=DeviceResetResponse)
async def reset_device(
    body: DeviceResetRequest,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> DeviceResetResponse:
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: device_reset(transport),
    )


__all__: list[str] = ["router"]
