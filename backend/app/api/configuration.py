"""Configuration API (Task 3.5): system info + IP + per-port + features/monitor/bob + QoS.

This router will grow across Task 3.5's five sub-tasks:

* 3.5a — system info + IP config
* 3.5b — per-port
* 3.5c — device-features / fault-detection / monitor / bob-ports
* 3.5d (this revision adds QoS: cos*, dscptable, diffserv, cosproto)
* 3.5e — support URLs

Endpoints
---------
Reads (13):
  GET  /api/v1/configuration/system           -> SystemInfoPage
  GET  /api/v1/configuration/ip               -> IpConfigPage
  GET  /api/v1/configuration/ports            -> PortConfigList
  GET  /api/v1/configuration/ports/{port}     -> PortForm
  GET  /api/v1/configuration/device-features  -> DeviceFeaturesPage
  GET  /api/v1/configuration/fault-detection  -> FaultDetectionPage
  GET  /api/v1/configuration/monitor          -> MonitorPage
  GET  /api/v1/configuration/bob-ports        -> BobPortsResponse
  GET  /api/v1/configuration/qos/cos          -> CosAppList
  GET  /api/v1/configuration/qos/user-pri     -> CosUserList
  GET  /api/v1/configuration/qos/vlan-pri     -> CosVlanList
  GET  /api/v1/configuration/qos/dscp         -> DscpTable
  GET  /api/v1/configuration/qos/diffserv     -> DiffservTable

Writes (15):
  PUT  /api/v1/configuration/system           -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/ip               -> ConfigWriteAck   (autobackup + host confirm, LOCKOUT-RISKY)
  PUT  /api/v1/configuration/gateway          -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/ports/{port}     -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/device-features  -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/fault-detection  -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/monitor          -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/bob-ports        -> ConfigWriteAck   (autobackup only)
  PUT  /api/v1/configuration/qos/cos          -> QosWriteAck      (autobackup only)
  PUT  /api/v1/configuration/qos/user-pri     -> QosWriteAck      (autobackup only)
  PUT  /api/v1/configuration/qos/vlan-pri     -> QosWriteAck      (autobackup only)
  PUT  /api/v1/configuration/qos/mode         -> QosWriteAck      (autobackup only)
  PUT  /api/v1/configuration/qos/dscp         -> QosWriteAck      (autobackup only, row-at-a-time)
  PUT  /api/v1/configuration/qos/diffserv     -> QosWriteAck      (autobackup only)
  PUT  /api/v1/configuration/qos/cos-proto    -> QosWriteAck      (autobackup only)

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
* ``PUT /qos/*`` — all QoS writes (application priority, user priority,
  VLAN priority, master mode, DSCP map, diffserv, protocol priority).
  None are lockout-risky: QoS is a forwarding-plane policy, not a
  management-plane control. Autobackup is the rollback path. The DSCP
  table is edited one row at a time (``set_dscptable`` takes a single
  ``(row_index, priority_8021p)`` pair) rather than the whole 64-entry
  table in one write.

Single-file design
------------------
Task 3.5's Phase 3 plan suggested splitting this module into a subpackage
once it grew past ~450 lines. We kept it as a single file because every
route handler calls an imported op symbol by name (``get_system_page``,
``set_cos_appt``, …) and the test suite monkey-patches those symbols on
this exact module. Splitting into ``configuration/system.py`` +
``configuration/qos.py`` would force every existing test to know which
sub-module owns each op and rewrite 31 patch calls. The docstring + grouped
sections keep the file navigable at its current ~700-line size.
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
from procurve_client.models.qos import (
    CosAppList,
    CosUserList,
    CosVlanList,
    DiffservTable,
    DscpTable,
    QosWriteAck,
    SetCosApptRequest,
    SetCosProtoRequest,
    SetCosTosModeRequest,
    SetCosUserPriRequest,
    SetCosVlanPriRequest,
    SetDiffservRequest,
    SetDscpTableRequest,
)
from procurve_client.operations.configuration import (
    get_bobports,
    get_cos_appt,
    get_cos_userpri,
    get_cos_vlanpri,
    get_devfeatures_page,
    get_diffserv,
    get_dscptable,
    get_faultdetect_page,
    get_ip_page,
    get_monitor_page,
    get_port_form,
    get_portscfg,
    get_system_page,
    set_bobports,
    set_cos_appt,
    set_cos_userpri,
    set_cos_vlanpri,
    set_cosproto,
    set_costos_mode,
    set_default_gateway,
    set_device_features,
    set_diffserv,
    set_dscptable,
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


# ---------------------------------------------------------------------------
# QoS — request bodies
# ---------------------------------------------------------------------------


class SetCosApptBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/cos`` — Add / Replace / Delete
    one application-priority row (``SetCosApptRequest.action``)."""

    request: SetCosApptRequest


class SetCosUserPriBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/user-pri``."""

    request: SetCosUserPriRequest


class SetCosVlanPriBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/vlan-pri``."""

    request: SetCosVlanPriRequest


class SetCosTosModeBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/mode`` — the master QoS mode
    (DISABLED / IP_PRECEDENCE / DIFFSERV)."""

    request: SetCosTosModeRequest


class SetDscpTableBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/dscp`` — one row of the
    64-entry DSCP → 802.1p map at a time (``row_index = codepoint + 1``)."""

    request: SetDscpTableRequest


class SetDiffservBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/diffserv``."""

    request: SetDiffservRequest


class SetCosProtoBody(BaseModel):
    """Body for ``PUT /api/v1/configuration/qos/cos-proto``."""

    request: SetCosProtoRequest


# ---------------------------------------------------------------------------
# QoS — reads
# ---------------------------------------------------------------------------


@router.get("/qos/cos", response_model=CosAppList)
async def read_qos_cos(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> CosAppList:
    """List application → priority entries (cos-app table)."""
    return await get_cos_appt(transport)


@router.get("/qos/user-pri", response_model=CosUserList)
async def read_qos_user_pri(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> CosUserList:
    """List per-device (IP) QoS entries."""
    return await get_cos_userpri(transport)


@router.get("/qos/vlan-pri", response_model=CosVlanList)
async def read_qos_vlan_pri(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> CosVlanList:
    """List per-VLAN QoS entries."""
    return await get_cos_vlanpri(transport)


@router.get("/qos/dscp", response_model=DscpTable)
async def read_qos_dscp(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> DscpTable:
    """Fetch the 64-row DSCP → 802.1p priority map."""
    return await get_dscptable(transport)


@router.get("/qos/diffserv", response_model=DiffservTable)
async def read_qos_diffserv(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> DiffservTable:
    """Fetch the 64-row inbound DiffServ policy table."""
    return await get_diffserv(transport)


# ---------------------------------------------------------------------------
# QoS — writes (all autobackup, none lockout-risky, no host confirm)
# ---------------------------------------------------------------------------


@router.put("/qos/cos", response_model=QosWriteAck)
async def write_qos_cos(
    body: SetCosApptBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Add / replace / delete an application-priority entry."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_cos_appt(transport, request=body.request),
    )


@router.put("/qos/user-pri", response_model=QosWriteAck)
async def write_qos_user_pri(
    body: SetCosUserPriBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Add / replace / delete a per-device QoS entry."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_cos_userpri(transport, request=body.request),
    )


@router.put("/qos/vlan-pri", response_model=QosWriteAck)
async def write_qos_vlan_pri(
    body: SetCosVlanPriBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Assign DSCP or 802.1p priority to a VLAN (mutually exclusive)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_cos_vlanpri(transport, request=body.request),
    )


@router.put("/qos/mode", response_model=QosWriteAck)
async def write_qos_mode(
    body: SetCosTosModeBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Set the switch-wide ToS interpretation mode (CoS vs DSCP master)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_costos_mode(transport, request=body.request),
    )


@router.put("/qos/dscp", response_model=QosWriteAck)
async def write_qos_dscp(
    body: SetDscpTableBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Update a single row of the DSCP → 802.1p map (``row_index`` = codepoint+1)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_dscptable(transport, request=body.request),
    )


@router.put("/qos/diffserv", response_model=QosWriteAck)
async def write_qos_diffserv(
    body: SetDiffservBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Rewrite the DSCP policy for an inbound codepoint."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_diffserv(transport, request=body.request),
    )


@router.put("/qos/cos-proto", response_model=QosWriteAck)
async def write_qos_cos_proto(
    body: SetCosProtoBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> QosWriteAck:
    """Submit the protocol-priority form (empty body on the 2810-24G)."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_cosproto(transport, request=body.request),
    )


__all__: list[str] = ["router"]
