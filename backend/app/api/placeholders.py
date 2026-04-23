"""Placeholder routers for tabs deferred to Phase 3+.

Each returns HTTP 501 with `{error: "not_implemented", phase: "3+"}`.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

configuration_router = APIRouter(prefix="/api/v1/configuration", tags=["placeholders"])
security_router = APIRouter(prefix="/api/v1/security", tags=["placeholders"])
diagnostics_router = APIRouter(prefix="/api/v1/diagnostics", tags=["placeholders"])
support_router = APIRouter(prefix="/api/v1/support", tags=["placeholders"])


def _not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail={"error": "not_implemented", "phase": "3+"},
    )


@configuration_router.get("")
async def configuration_placeholder() -> None:
    _not_implemented()


@security_router.get("")
async def security_placeholder() -> None:
    _not_implemented()


@diagnostics_router.get("")
async def diagnostics_placeholder() -> None:
    _not_implemented()


@support_router.get("")
async def support_placeholder() -> None:
    _not_implemented()
