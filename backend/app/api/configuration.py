"""Configuration API (Task 3.5): system info + IP config (sub-task 3.5a).

This router will grow across Task 3.5's five sub-tasks:

* 3.5a (this file's initial state) — system info + IP config
* 3.5b — per-port configuration (ports sub-tab)
* 3.5c — device features (IGMP / STP)
* 3.5d — QoS (cos*, dscptable, diffserv)
* 3.5e — support URLs

Endpoints (this sub-task)
-------------------------
Reads (2):
  GET  /api/v1/configuration/system  -> SystemInfoPage
  GET  /api/v1/configuration/ip      -> IpConfigPage

Writes (3):
  PUT  /api/v1/configuration/system   -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/ip       -> ConfigWriteAck   (autobackup + host confirm, LOCKOUT-RISKY)
  PUT  /api/v1/configuration/gateway  -> ConfigWriteAck   (autobackup only)

Write-safety policy
-------------------
All three writes are wrapped in :func:`app.write_safety.write_with_autobackup`,
which takes a pre-write backup before any switch write is attempted.

* ``PUT /system`` — name / location / contact are cosmetic SNMP strings.
  They cannot lock the operator out of the switch, so no
  ``require_host_confirmation`` gate.
* ``PUT /ip`` — changes the management IP / VLAN / DHCP mode.  Getting any
  of these wrong can immediately sever the operator's session to the
  switch.  Gated with ``require_host_confirmation``: the caller must type
  the current ``SWITCH_HOST`` before the request is accepted.
* ``PUT /gateway`` — **decision: no host-confirmation.** A wrong gateway
  breaks external routing but does not sever the operator's LAN session
  to the switch (the TCP connection over the directly-attached VLAN
  survives). The pre-write backup is considered sufficient rollback. If
  operator feedback surfaces near-miss incidents we can tighten this to
  require confirmation later.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.backup_store import BackupStore
from app.deps import get_app_settings, get_backup_store, get_transport
from app.settings import Settings
from app.write_safety import require_host_confirmation, write_with_autobackup
from procurve_client.models.network import (
    ConfigWriteAck,
    IpConfigPage,
    SetDefaultGatewayRequest,
    SetIpConfigRequest,
    SetSystemInfoRequest,
    SystemInfoPage,
)
from procurve_client.operations.configuration import (
    get_ip_page,
    get_system_page,
    set_default_gateway,
    set_ip_config,
    set_system_info,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/configuration", tags=["configuration"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class SetSystemInfoBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/system``.

    No ``confirm_switch_host`` — SNMP name / location / contact are not
    lockout-risky.
    """

    request: SetSystemInfoRequest


class SetIpConfigBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/ip``.

    ``request`` carries the full :class:`SetIpConfigRequest` the procurve op
    expects; ``confirm_switch_host`` gates against accidentally severing the
    operator's session to the switch.
    """

    request: SetIpConfigRequest
    confirm_switch_host: str


class SetDefaultGatewayBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/gateway``.

    No host confirmation — see module docstring for the trade-off.
    """

    request: SetDefaultGatewayRequest


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/system", response_model=SystemInfoPage)
async def read_system(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> SystemInfoPage:
    return await get_system_page(transport)


@router.get("/ip", response_model=IpConfigPage)
async def read_ip(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> IpConfigPage:
    return await get_ip_page(transport)


# ---------------------------------------------------------------------------
# Writes (all autobackup; /ip also requires host confirmation)
# ---------------------------------------------------------------------------


@router.put("/system", response_model=ConfigWriteAck)
async def write_system(
    body: SetSystemInfoBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Write system name / location / contact.

    Not lockout-risky — the pre-write backup is sufficient rollback.
    """
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_system_info(transport, request=body.request),
    )


@router.put("/ip", response_model=ConfigWriteAck)
async def write_ip(
    body: SetIpConfigBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Write the management-interface IP configuration.

    LOCKOUT RISK: changing VLAN / mode / gateway on the management
    interface can sever the operator's TCP session to the switch
    instantly.  Gated with ``require_host_confirmation``.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_ip_config(transport, request=body.request),
    )


@router.put("/gateway", response_model=ConfigWriteAck)
async def write_gateway(
    body: SetDefaultGatewayBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Set only the default gateway.

    A wrong gateway breaks external routing but the operator's direct
    LAN session to the switch survives — no host confirmation (see
    module docstring for the trade-off).
    """
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_default_gateway(transport, request=body.request),
    )


__all__: list[str] = ["router"]
