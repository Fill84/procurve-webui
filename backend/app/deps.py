"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import cast

from fastapi import Depends, HTTPException, Request, status

from app import auth as auth_module
from app.auth import SESSION_COOKIE, SessionEntry, SessionStore
from app.settings import Settings
from procurve_client.transport import ProcurveTransport


def _get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _get_store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)


async def get_session(request: Request) -> SessionEntry:
    """Validate cookie + lookup the live session entry."""
    settings = _get_settings(request)
    store = _get_store(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no session")
    max_age = settings.session_ttl_hours * 3600
    session_id = store.unsign(token, max_age_seconds=max_age)
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad session")
    entry = store.get(session_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown session")
    if entry.expires_at <= auth_module._now():
        # Expired: release the transport and remove the entry, then 401.
        await store.drop(session_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
    return entry


async def get_transport(
    session: SessionEntry = Depends(get_session),  # noqa: B008 — FastAPI pattern
) -> ProcurveTransport:
    return session.transport
