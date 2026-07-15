"""VLAN API (Phase 4, F1): list, membership, create / delete / rename,
per-port membership changes.

Endpoints
---------
Reads (2):
  GET  /api/v1/vlans                    -> VlanList        (getVLANAll)
  GET  /api/v1/vlans/{vlan_id}/ports    -> VlanMembershipList (getVLANPort)

Writes (4):
  POST /api/v1/vlans                    -> VlanWriteAck    (addVLAN)
  POST /api/v1/vlans/delete             -> VlanWriteAck    (delVLAN, multi-id)
  PUT  /api/v1/vlans/{vlan_id}/name     -> VlanWriteAck    (renVLAN)
  PUT  /api/v1/vlans/{vlan_id}/ports    -> VlanWriteAck    (setVLANPort)

Write-safety policy
-------------------
Spec §8.3 classes VLAN membership in the "careful" tier. EVERY write here
takes the full lockout-risky gate — ``require_host_confirmation`` +
``write_with_autobackup`` — because each one can sever the operator's own
management path: deleting (or renaming away from) the VLAN that carries
management traffic, or flipping the untagged membership of the uplink port
you are connected through, drops this UI's connectivity immediately.

Deliberately NOT exposed:
  * ``setVLANMode`` — requires a device reboot to take effect and its error
    body shape is unverified ("needs live capture" in the protocol docs).
  * ``setPrimary`` — moves the switch's management/primary VLAN; error
    shape also unverified live.
  * GVRP mode / per-port GVRP writes — secondary feature, error shapes
    unverified. Reads for these can land alongside if the UI grows a GVRP
    panel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.backup_store import BackupStore
from app.deps import get_app_settings, get_backup_store, get_transport
from app.settings import Settings
from app.write_safety import require_host_confirmation, write_with_autobackup
from procurve_client.models.vlan import (
    AddVlanRequest,
    DelVlanRequest,
    RenVlanRequest,
    SetVlanPortsRequest,
    VlanList,
    VlanMembershipList,
    VlanWriteAck,
)
from procurve_client.operations.vlan import (
    add_vlan,
    delete_vlans,
    get_vlan_ports,
    get_vlans_all,
    rename_vlan,
    set_vlan_ports,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/vlans", tags=["vlans"])


# ---------------------------------------------------------------------------
# Request bodies (every write carries `confirm_switch_host`)
# ---------------------------------------------------------------------------


class AddVlanBody(BaseModel):
    """Body for ``POST /api/v1/vlans``."""

    request: AddVlanRequest
    confirm_switch_host: str


class DelVlanBody(BaseModel):
    """Body for ``POST /api/v1/vlans/delete``.

    A dedicated action path instead of ``DELETE /vlans`` because the applet
    (and the wire CGI) support multi-select delete, which needs a body.
    """

    request: DelVlanRequest
    confirm_switch_host: str


class RenVlanBody(BaseModel):
    """Body for ``PUT /api/v1/vlans/{vlan_id}/name``."""

    vlan_name: str
    confirm_switch_host: str


class SetVlanPortsBody(BaseModel):
    """Body for ``PUT /api/v1/vlans/{vlan_id}/ports``.

    ``changes`` should contain only the ports whose mode actually changed
    (mirroring the applet's ``getChangedPortsID``) — the request model
    enforces at least one entry.
    """

    request: SetVlanPortsRequest
    confirm_switch_host: str


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("", response_model=VlanList)
async def read_vlans(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> VlanList:
    """Full per-VLAN metadata (name, type, tagged/untagged/forbid port sets)."""
    return await get_vlans_all(transport)


@router.get("/{vlan_id}/ports", response_model=VlanMembershipList)
async def read_vlan_ports(
    vlan_id: int,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> VlanMembershipList:
    """Per-port membership modes for one VLAN (0=Auto/No 1=Tagged 2=Untagged 3=Forbid)."""
    return await get_vlan_ports(transport, vlan_id=vlan_id)


# ---------------------------------------------------------------------------
# Writes (all: host confirmation + pre-write autobackup)
# ---------------------------------------------------------------------------


@router.post("", response_model=VlanWriteAck)
async def create_vlan(
    body: AddVlanBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> VlanWriteAck:
    """Create a static VLAN. Switch-reported validation errors surface verbatim."""
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: add_vlan(transport, request=body.request),
    )


@router.post("/delete", response_model=VlanWriteAck)
async def remove_vlans(
    body: DelVlanBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> VlanWriteAck:
    """Delete one or more VLANs.

    LOCKOUT RISK: deleting the VLAN that carries management traffic (or the
    primary VLAN) severs this UI's own path to the switch. The firmware
    rejects some of these itself — its error message is surfaced verbatim.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: delete_vlans(transport, request=body.request),
    )


@router.put("/{vlan_id}/name", response_model=VlanWriteAck)
async def write_vlan_name(
    vlan_id: int,
    body: RenVlanBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> VlanWriteAck:
    """Rename a VLAN. The path ``vlan_id`` is authoritative."""
    require_host_confirmation(body.confirm_switch_host, settings)
    request = RenVlanRequest(vlan_id=vlan_id, vlan_name=body.vlan_name)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: rename_vlan(transport, request=request),
    )


@router.put("/{vlan_id}/ports", response_model=VlanWriteAck)
async def write_vlan_ports(
    vlan_id: int,
    body: SetVlanPortsBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> VlanWriteAck:
    """Apply per-port membership changes for one VLAN.

    LOCKOUT RISK: removing the untagged membership of the port your own
    client reaches the switch through cuts this UI off mid-request. The
    route ``vlan_id`` is authoritative and overrides the body's copy.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    request = body.request.model_copy(update={"vlan_id": vlan_id})
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_vlan_ports(transport, request=request),
    )


__all__: list[str] = ["router"]
