"""Placeholder routers for tabs deferred to Phase 3+.

Each returns HTTP 501 with `{error: "not_implemented", phase: "3+"}`.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_NOT_IMPLEMENTED_BODY = {"error": "not_implemented", "phase": "3+"}


def _not_implemented_response() -> JSONResponse:
    return JSONResponse(status_code=501, content=_NOT_IMPLEMENTED_BODY)


configuration_router = APIRouter(prefix="/api/v1/configuration", tags=["placeholders"])
security_router = APIRouter(prefix="/api/v1/security", tags=["placeholders"])


@configuration_router.get("")
async def configuration_placeholder() -> JSONResponse:
    return _not_implemented_response()


@security_router.get("")
async def security_placeholder() -> JSONResponse:
    return _not_implemented_response()
