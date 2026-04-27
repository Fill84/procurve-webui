"""Security API (Task 3.4): web access, authorized managers, per-port security,
intrusion log, SSL state, device passwords.

Endpoints
---------
Reads (5):
  GET  /api/v1/security/web-access    -> WebAccessPage
  GET  /api/v1/security/web-managers  -> WebManagersResponse
  GET  /api/v1/security/per-port      -> PerportsResponse    (optional ?group=)
  GET  /api/v1/security/intrusion     -> IntrusionLogResponse
  GET  /api/v1/security/ssl-state     -> SSLState

Writes (5):
  PUT  /api/v1/security/web-access        -> SetSSLResponse              (LOCKOUT-RISKY)
  POST /api/v1/security/web-managers      -> SetWebManagerResponse       (LOCKOUT-RISKY)
  PUT  /api/v1/security/device-passwords  -> SetDevicePasswordsResponse  (LOCKOUT-RISKY)
  PUT  /api/v1/security/per-port/{port}   -> SetPerportResponse
  POST /api/v1/security/intrusion/reset   -> ResetIntrusionFlagsResponse

Write-safety policy
-------------------
All five writes go through :func:`app.write_safety.write_with_autobackup`,
which takes a pre-write backup *before* any switch write is issued.

The three lockout-risky writes (web-access / web-managers / device-passwords)
additionally require :func:`require_host_confirmation` — the caller must
type the current ``SWITCH_HOST`` into ``confirm_switch_host`` before the
request is accepted. The other two (per-port, intrusion-reset) do not
reach that bar: per-port tweaks are reversible via the pre-write backup,
and intrusion-reset only clears cosmetic alert flags.

``device-passwords`` is the most lockout-risky write of the three: a
mistyped Manager password is recoverable only via a physical
factory-reset of the switch. The firmware also transmits the new password
cleartext in the URL query string — a 2810 protocol flaw that we mirror
faithfully. The UI must surface both risks before submitting.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.backup_store import BackupStore
from app.deps import get_app_settings, get_backup_store, get_transport
from app.settings import Settings
from app.write_safety import require_host_confirmation, write_with_autobackup
from procurve_client.models.security import (
    IntrusionLogResponse,
    PerportsResponse,
    ResetIntrusionFlagsResponse,
    SetDevicePasswordsRequest,
    SetDevicePasswordsResponse,
    SetPerportRequest,
    SetPerportResponse,
    SetSSLRequest,
    SetSSLResponse,
    SetWebManagerRequest,
    SetWebManagerResponse,
    SSLState,
    WebAccessPage,
    WebManagersResponse,
)
from procurve_client.operations.security import (
    get_intrusion,
    get_perports,
    get_ssl_state,
    get_web_access_page,
    get_web_managers,
    reset_intrusion_flags,
    set_device_passwords,
    set_perport,
    set_ssl,
    set_web_manager,
)
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/security", tags=["security"])


# ---------------------------------------------------------------------------
# Request bodies (lockout-risky writes carry `confirm_switch_host`)
# ---------------------------------------------------------------------------


class SetSSLBody(BaseModel):
    """Body for ``PUT /api/v1/security/web-access``.

    ``request`` is the full :class:`SetSSLRequest` the procurve op expects;
    ``confirm_switch_host`` gates against accidental HTTPS-only lockouts.
    """

    request: SetSSLRequest
    confirm_switch_host: str


class SetWebManagerBody(BaseModel):
    """Body for ``POST /api/v1/security/web-managers``.

    ``request`` is the add/replace/delete discriminated union;
    ``confirm_switch_host`` gates against accidental management-IP lockouts.
    """

    request: SetWebManagerRequest
    confirm_switch_host: str


class SetDevicePasswordsBody(BaseModel):
    """Body for ``PUT /api/v1/security/device-passwords``.

    ``request`` carries the four credential pairs (Operator + Manager
    username / password / confirm). ``confirm_switch_host`` gates against
    casual mis-clicks — recovery from a wrong Manager password is
    physical-factory-reset only.
    """

    request: SetDevicePasswordsRequest
    confirm_switch_host: str


class SetPerportBody(BaseModel):
    """Body for ``PUT /api/v1/security/per-port/{port}``.

    No host confirmation — per-port security tweaks are reversible via the
    pre-write backup and are not lockout-risky.
    """

    request: SetPerportRequest


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/web-access", response_model=WebAccessPage)
async def read_web_access(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> WebAccessPage:
    return await get_web_access_page(transport)


@router.get("/web-managers", response_model=WebManagersResponse)
async def read_web_managers(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> WebManagersResponse:
    return await get_web_managers(transport)


@router.get("/per-port", response_model=PerportsResponse)
async def read_per_port(
    group: str = "",
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> PerportsResponse:
    return await get_perports(transport, group=group)


@router.get("/intrusion", response_model=IntrusionLogResponse)
async def read_intrusion(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> IntrusionLogResponse:
    return await get_intrusion(transport)


@router.get("/ssl-state", response_model=SSLState)
async def read_ssl_state(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
) -> SSLState:
    return await get_ssl_state(transport)


# ---------------------------------------------------------------------------
# Writes (all autobackup; lockout-risky ones also require host confirm)
# ---------------------------------------------------------------------------


@router.put("/web-access", response_model=SetSSLResponse)
async def write_web_access(
    body: SetSSLBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> SetSSLResponse:
    """Configure the SSL subsystem (HTTPS on/off, port, cert mode).

    LOCKOUT RISK: enabling HTTPS-only without a valid certificate
    installed will lock you out of the web UI. The browser will refuse
    to present the self-signed cert without an override, and the
    firmware does not fall back to HTTP while HTTPS is on. Keep an SSH
    session open before toggling this.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_ssl(transport, request=body.request),
    )


@router.post("/web-managers", response_model=SetWebManagerResponse)
async def write_web_managers(
    body: SetWebManagerBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> SetWebManagerResponse:
    """Add / replace / delete an authorized-manager IP entry.

    LOCKOUT RISK: the Authorized-Manager list is a whitelist. Adding an
    entry that excludes your client IP (or deleting your own row) locks
    you out of the web UI immediately, with no graceful back-off.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_web_manager(transport, request=body.request),
    )


@router.put("/device-passwords", response_model=SetDevicePasswordsResponse)
async def write_device_passwords(
    body: SetDevicePasswordsBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> SetDevicePasswordsResponse:
    """Change Operator and Manager credentials.

    LOCKOUT RISK (most severe of the three): if you mistype the Manager
    password — or supply a non-matching confirm — recovery requires a
    physical factory-reset of the switch. There is no software path back
    in. The firmware also ships the new password cleartext in the URL
    query string (a 2810 protocol flaw mirrored faithfully); send this
    request only over a trusted link or with HTTPS terminated upstream.

    Gated like the other lockout-risky writes: ``confirm_switch_host``
    must match ``settings.switch_host``, and a pre-write backup is taken
    before the credential change is issued.
    """
    require_host_confirmation(body.confirm_switch_host, settings)
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_device_passwords(transport, request=body.request),
    )


@router.put("/per-port/{port}", response_model=SetPerportResponse)
async def write_per_port(
    port: int,
    body: SetPerportBody,
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> SetPerportResponse:
    """Configure one port's security policy.

    Not lockout-risky — the pre-write backup is sufficient rollback.
    The path param ``port`` must match ``body.request.port``; a mismatch
    is a client-side mistake and we do not silently coerce it.
    """
    # The route port is authoritative: rebuild the request model so the
    # URL and body agree even if the caller submitted a stale body.
    request = body.request.model_copy(update={"port": port})
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: set_perport(transport, request=request),
    )


@router.post("/intrusion/reset", response_model=ResetIntrusionFlagsResponse)
async def write_intrusion_reset(
    transport: ProcurveTransport = Depends(get_transport),  # noqa: B008
    settings: Settings = Depends(get_app_settings),  # noqa: B008
    store: BackupStore = Depends(get_backup_store),  # noqa: B008
) -> ResetIntrusionFlagsResponse:
    """Clear cosmetic intrusion alert flags. Low risk — still autobacked."""
    return await write_with_autobackup(
        settings=settings,
        store=store,
        transport=transport,
        write=lambda: reset_intrusion_flags(transport),
    )


__all__: list[str] = ["router"]
