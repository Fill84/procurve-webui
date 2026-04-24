"""Configuration API (Task 3.5): system info + IP + per-port + features/monitor/bob.

This router will grow across Task 3.5's five sub-tasks:

* 3.5a — system info + IP config
* 3.5b — per-port
* 3.5c (this revision adds device-features / fault-detection / monitor / bob-ports)
* 3.5d — QoS (cos*, dscptable, diffserv)
* 3.5e — support URLs

Endpoints
---------
Reads (8):
  GET  /api/v1/configuration/system           -> SystemInfoPage
  GET  /api/v1/configuration/ip               -> IpConfigPage
  GET  /api/v1/configuration/ports            -> PortConfigList
  GET  /api/v1/configuration/ports/{port}     -> PortForm
  GET  /api/v1/configuration/device-features  -> DeviceFeaturesPage
  GET  /api/v1/configuration/fault-detection  -> FaultDetectionPage
  GET  /api/v1/configuration/monitor          -> MonitorPage
  GET  /api/v1/configuration/bob-ports        -> BobPortsResponse

Writes (8):
  PUT  /api/v1/configuration/system           -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/ip               -> ConfigWriteAck   (autobackup + host confirm, LOCKOUT-RISKY)
  PUT  /api/v1/configuration/gateway          -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/ports/{port}     -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/device-features  -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/fault-detection  -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/monitor          -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/bob-ports        -> ConfigWriteAck   (autobackup only)

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
* ``PUT /ports/{port}`` — no host confirmation. Per-port enable / name /
  speed / flow-control changes are reversible via the pre-write backup
  and are not lockout-risky in typical deployments. The path ``port``
  is authoritative: we rebuild the request model so the URL and body
  agree even if the caller submitted a stale ``request.ports`` list
  (mirrors the Security tab's per-port endpoint).
* ``PUT /device-features`` — IGMP / Spanning Tree toggles. Not lockout
  risky in the sense that the management session survives; autobackup
  is sufficient rollback.
* ``PUT /fault-detection`` — sensitivity is a local telemetry filter;
  changing it cannot sever the management session.
* ``PUT /monitor`` — port-mirroring enable + destination / source mask.
  Not lockout risky. (Destination port receives mirrored traffic; it is
  not taken down as a data path.)
* ``PUT /bob-ports`` — bulk enable / disable of admin status on a set of
  ports (the device-view button). The operator's own uplink port being
  included in a disable set would break the session, but that failure
  mode is symmetric with the per-port endpoint which also takes no host
  confirmation. Autobackup is the rollback path.
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
    DeviceFeaturesPage,
    FaultDetectionPage,
    IpConfigPage,
    MonitorPage,
    SetDefaultGatewayRequest,
    SetDeviceFeaturesRequest,
    SetFaultDetectionRequest,
    SetIpConfigRequest,
    SetMonitorRequest,
    SetSystemInfoRequest,
    SystemInfoPage,
)
from procurve_client.models.port import (
    BobPortsResponse,
    PortConfigList,
    PortForm,
    SetBobPortsRequest,
    SetPortConfigRequest,
)
from procurve_client.operations.configuration import (
    get_bobports,
    get_devfeatures_page,
    get_faultdetect_page,
    get_ip_page,
    get_monitor_page,
    get_port_form,
    get_portscfg,
    get_system_page,
    set_bobports,
    set_default_gateway,
    set_device_features,
    set_fault_detection,
    set_ip_config,
    set_monitor,
    set_port_config,
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


class SetPortConfigBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/ports/{port}``.

    No ``confirm_switch_host`` — per-port tweaks are reversible via the
    pre-write autobackup and are not lockout-risky. The route handler
    rebuilds ``request.ports`` from the path ``{port}`` to prevent a stale
    body targeting the wrong port; the body's ``ports`` field is ignored
    in favour of the URL.
    """

    request: SetPortConfigRequest


class SetDeviceFeaturesBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/device-features``."""

    request: SetDeviceFeaturesRequest


class SetFaultDetectionBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/fault-detection``."""

    request: SetFaultDetectionRequest


class SetMonitorBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/monitor``."""

    request: SetMonitorRequest


class SetBobPortsBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/bob-ports``."""

    request: SetBobPortsRequest


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


@router.get("/ports", response_model=PortConfigList)
async def read_ports(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> PortConfigList:
    """List every port's current configuration."""
    return await get_portscfg(transport)


@router.get("/ports/{port}", response_model=PortForm)
async def read_port_form(
    port: int,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> PortForm:
    """Fetch the edit-form state for a single port.

    The underlying procurve op supports multi-port selection; Phase 3
    exposes single-port reads only. Multi-port bulk edits can be added
    later if the UI ever needs them.
    """
    return await get_port_form(transport, ports=[port])


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


@router.put("/ports/{port}", response_model=ConfigWriteAck)
async def write_port_config(
    port: int,
    body: SetPortConfigBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Write per-port configuration (enable / name / speed / flow-control).

    The URL ``{port}`` is authoritative: we rebuild the request so the
    path and body agree even if the caller submitted a stale body with
    ``request.ports`` targeting a different port. Not lockout-risky —
    the pre-write autobackup is sufficient rollback.
    """
    pinned = body.request.model_copy(update={"ports": [port]})
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_port_config(transport, request=pinned),
    )


# ---------------------------------------------------------------------------
# Device features / fault detection / monitor / bob-ports (reads)
# ---------------------------------------------------------------------------


@router.get("/device-features", response_model=DeviceFeaturesPage)
async def read_device_features(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> DeviceFeaturesPage:
    """Read IGMP / Spanning-Tree flags + VLAN count."""
    return await get_devfeatures_page(transport)


@router.get("/fault-detection", response_model=FaultDetectionPage)
async def read_fault_detection(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> FaultDetectionPage:
    """Read fault-detection sensitivity."""
    return await get_faultdetect_page(transport)


@router.get("/monitor", response_model=MonitorPage)
async def read_monitor(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> MonitorPage:
    """Read port-mirroring state (enabled, candidate + selected dest port)."""
    return await get_monitor_page(transport)


@router.get("/bob-ports", response_model=BobPortsResponse)
async def read_bob_ports(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> BobPortsResponse:
    """Device-view port rollup (admin status per port + link state)."""
    return await get_bobports(transport)


# ---------------------------------------------------------------------------
# Device features / fault detection / monitor / bob-ports (writes)
# ---------------------------------------------------------------------------


@router.put("/device-features", response_model=ConfigWriteAck)
async def write_device_features(
    body: SetDeviceFeaturesBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Write IGMP / Spanning Tree flags. Not lockout-risky."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_device_features(transport, request=body.request),
    )


@router.put("/fault-detection", response_model=ConfigWriteAck)
async def write_fault_detection(
    body: SetFaultDetectionBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Write fault-detection sensitivity (one of FaultSensitivity)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_fault_detection(transport, request=body.request),
    )


@router.put("/monitor", response_model=ConfigWriteAck)
async def write_monitor(
    body: SetMonitorBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Enable / disable port mirroring (dest + source mask required when on)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_monitor(transport, request=body.request),
    )


@router.put("/bob-ports", response_model=ConfigWriteAck)
async def write_bob_ports(
    body: SetBobPortsBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ConfigWriteAck:
    """Bulk-enable / disable admin status on a set of ports."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_bobports(transport, request=body.request),
    )


__all__: list[str] = ["router"]
