"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.backups import router as backups_router
from app.api.configuration import router as configuration_router
from app.api.diagnostics import router as diagnostics_router
from app.api.health import router as health_router
from app.api.identity import router as identity_router
from app.api.security import router as security_router
from app.api.status import router as status_router
from app.api.support import router as support_router
from app.auth import SessionStore
from app.backup_store import BackupStore
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.settings import Settings
from app.static import mount_static
from app.ws.port_traffic import port_traffic_ws


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = Settings()
    app.state.settings = settings
    app.state.session_store = SessionStore(secret=settings.session_secret)
    app.state.backup_store = BackupStore(root=settings.backups_dir)
    try:
        yield
    finally:
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


def create_app(dist_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="procurve-webui", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(identity_router)
    app.include_router(status_router)
    app.include_router(health_router)
    app.include_router(backups_router)
    app.include_router(configuration_router)
    app.include_router(security_router)
    app.include_router(diagnostics_router)
    app.include_router(support_router)
    app.add_api_websocket_route("/ws/port-traffic", port_traffic_ws)
    # MUST be last: SPA fallback is a catch-all GET and would shadow API/WS
    # routes if registered earlier.
    mount_static(app, dist_dir if dist_dir is not None else _resolve_dist_dir())
    return app


app = create_app()
