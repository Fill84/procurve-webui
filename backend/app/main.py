"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.auth import SessionStore
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = Settings()
    app.state.settings = settings
    app.state.session_store = SessionStore(secret=settings.session_secret)
    try:
        yield
    finally:
        # Shut down every cached transport so we don't leak httpx clients.
        await app.state.session_store.close_all()


def create_app() -> FastAPI:
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
    return app


app = create_app()
