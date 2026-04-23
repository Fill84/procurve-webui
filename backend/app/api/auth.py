"""Auth endpoints: login, logout, whoami (spec §11.3)."""
from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, SessionEntry, SessionStore, create_session
from app.deps import get_session
from app.settings import Settings
from procurve_client.errors import AuthError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    session_id: str
    expires_at: datetime


class WhoamiResponse(BaseModel):
    username: str
    expires_at: datetime


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
    try:
        entry = await create_session(
            store=store,
            username=payload.username,
            password=payload.password,
            settings=settings,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        ) from exc

    signed = store.sign(entry.session_id)
    _set_cookie(response, signed, max_age_seconds=settings.session_ttl_hours * 3600)
    return LoginResponse(session_id=entry.session_id, expires_at=entry.expires_at)


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
    session: SessionEntry = Depends(get_session),  # noqa: B008 — FastAPI pattern
) -> WhoamiResponse:
    return WhoamiResponse(username=session.username, expires_at=session.expires_at)
