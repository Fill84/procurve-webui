"""Auth endpoints: login, logout, whoami (spec §11.3)."""
from __future__ import annotations

import math
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE,
    LoginThrottle,
    SessionEntry,
    SessionStore,
    create_session,
)
from app.deps import get_session
from app.settings import Settings
from procurve_client.errors import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    # The signed session rides ONLY in the httponly cookie. The raw
    # session_id used to be echoed here too — needlessly handing the
    # unsigned half of the credential to page JavaScript.
    expires_at: datetime


class WhoamiResponse(BaseModel):
    username: str
    expires_at: datetime
    # Client address as seen by the backend. Lets the UI warn when an
    # authorized-managers change would exclude the operator's own IP
    # (advisory only — a reverse proxy in front makes this the proxy IP).
    client_ip: str | None = None


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _store(request: Request) -> SessionStore:
    return cast(SessionStore, request.app.state.session_store)


def _set_cookie(response: Response, signed: str, max_age_seconds: int) -> None:
    # Secure=False while we run plain HTTP inside Docker. Flip to True behind a
    # TLS-terminating reverse proxy (e.g. Traefik) in deployment.
    response.set_cookie(
        key=SESSION_COOKIE,
        value=signed,
        max_age=max_age_seconds,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request, payload: LoginRequest, response: Response
) -> LoginResponse:
    settings = _settings(request)
    store = _store(request)
    throttle = cast(LoginThrottle, request.app.state.login_throttle)
    client_key = request.client.host if request.client else "unknown"

    # Backoff gate BEFORE any switch I/O: every credential check is a live
    # probe against the fragile switch, so brute force is a hardware hazard
    # as much as a security one.
    retry_after = math.ceil(throttle.retry_after_seconds(client_key))
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"too many failed login attempts; retry in {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        entry = await create_session(
            store=store,
            username=payload.username,
            password=payload.password,
            settings=settings,
        )
    except AuthError as exc:
        throttle.record_failure(client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        ) from exc

    throttle.record_success(client_key)
    signed = store.sign(entry.session_id)
    _set_cookie(response, signed, max_age_seconds=settings.session_ttl_hours * 3600)
    return LoginResponse(expires_at=entry.expires_at)


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    store = _store(request)
    settings = _settings(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session_id = store.unsign(token, max_age_seconds=settings.session_ttl_hours * 3600)
        if session_id is not None:
            await store.drop(session_id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(
    request: Request,
    session: SessionEntry = Depends(get_session),  # noqa: B008 — FastAPI pattern
) -> WhoamiResponse:
    return WhoamiResponse(
        username=session.username,
        expires_at=session.expires_at,
        client_ip=request.client.host if request.client else None,
    )
