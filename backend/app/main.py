"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from app.api.auth import router as auth_router
from app.api.backups import router as backups_router
from app.api.configuration import router as configuration_router
from app.api.diagnostics import router as diagnostics_router
from app.api.health import HealthProbeCache
from app.api.health import router as health_router
from app.api.identity import router as identity_router
from app.api.security import router as security_router
from app.api.status import router as status_router
from app.api.support import router as support_router
from app.api.vlan import router as vlan_router
from app.auth import LoginThrottle, SessionStore
from app.backup_store import BackupStore
from app.csrf import install_csrf_protection
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.security_headers import install_security_headers
from app.settings import Settings
from app.static import mount_static
from app.ws.port_traffic import PortTrafficBroadcaster, port_traffic_ws


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = Settings()
    app.state.settings = settings
    app.state.session_store = SessionStore(secret=settings.session_secret)
    app.state.backup_store = BackupStore(root=settings.backups_dir)
    app.state.login_throttle = LoginThrottle()
    _warn_if_backups_dir_not_writable(settings)
    # One shared switch poller for all /ws/port-traffic clients: switch load
    # stays constant regardless of how many tabs are open (read-safety rule).
    app.state.port_traffic = PortTrafficBroadcaster(
        settings=settings, store=app.state.session_store
    )
    app.state.health_cache = HealthProbeCache()
    try:
        yield
    finally:
        await app.state.port_traffic.aclose()
        await app.state.health_cache.aclose()
        # Shut down every cached transport so we don't leak httpx clients.
        await app.state.session_store.close_all()


def _resolve_dist_dir() -> Path:
    """Best-effort resolution of the frontend dist dir at app-creation time.

    Prefers `Settings().frontend_dist` when the env is populated, but silently
    falls back to the default path literal if required env is missing (e.g.
    during the module-level `app = create_app()` that runs on plain import
    with no SWITCH_HOST / SESSION_SECRET set). The static mount itself is a
    no-op when the returned path does not exist, so a stale fallback is safe.
    """
    try:
        return Settings().frontend_dist
    except Exception:  # noqa: BLE001 — env may be unset at import time
        return Path("/app/frontend/dist")


def _warn_if_backups_dir_not_writable(settings: Settings) -> None:
    """Loud startup warning when pre-write backups cannot be persisted.

    On a native-Linux host the bind-mounted ./backups may not be writable by
    the non-root container user — in that state EVERY switch write is
    blocked (fail-safe, the autobackup gate refuses), which would otherwise
    surface only as confusing per-request failures.
    """
    probe = settings.backups_dir / ".write-probe"
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as exc:
        structlog.get_logger().warning(
            "backups_dir_not_writable",
            path=str(settings.backups_dir),
            error=str(exc),
            detail=(
                "pre-write backups will fail, so ALL switch writes will be "
                "blocked; fix the volume ownership/permissions"
            ),
        )


def create_app(dist_dir: Path | None = None) -> FastAPI:
    # NOTE: no CORS middleware — this is a strictly same-origin app (the
    # FastAPI process serves the SPA itself). The previous CORSMiddleware
    # had allow_origins=[] and was dead configuration; cross-origin writes
    # are actively rejected by app/csrf.py instead.
    app = FastAPI(title="procurve-webui", version="0.1.2", lifespan=lifespan)
    install_error_handlers(app)
    install_security_headers(app)
    install_csrf_protection(app)
    # Compress SPA bundles + larger JSON payloads. No BREACH exposure: no
    # secret (session cookie, CSRF token) is ever reflected in a response
    # body alongside attacker-controlled input.
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.include_router(auth_router)
    app.include_router(identity_router)
    app.include_router(status_router)
    app.include_router(health_router)
    app.include_router(backups_router)
    app.include_router(configuration_router)
    app.include_router(security_router)
    app.include_router(diagnostics_router)
    app.include_router(support_router)
    app.include_router(vlan_router)
    app.add_api_websocket_route("/ws/port-traffic", port_traffic_ws)
    # MUST be last: SPA fallback is a catch-all GET and would shadow API/WS
    # routes if registered earlier.
    mount_static(app, dist_dir if dist_dir is not None else _resolve_dist_dir())
    return app


app = create_app()
