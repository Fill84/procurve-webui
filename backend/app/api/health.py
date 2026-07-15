"""Health endpoints — process liveness and (cached) switch reachability.

Two probes with very different costs:

* ``GET /api/v1/health/live`` — pure process liveness. Returns 200 as long
  as uvicorn answers. **Never touches the switch.** This is what the Docker
  HEALTHCHECK uses, so container monitoring produces zero switch traffic
  (read-safety rule: this switch has crashed under repeated probing).
* ``GET /api/v1/health`` — switch reachability, served from a small cache.
  A real probe (``GET /home.html`` via a single long-lived ``NoneAuth``
  transport) runs at most once per ``_PROBE_TTL_SECONDS``; concurrent
  callers coalesce onto one in-flight probe via a lock. An aggressive
  external monitor therefore cannot translate 1:1 into switch requests.

Both endpoints are unauthenticated (they exist for monitoring). Neither
leaks anything beyond an ok/unreachable verdict.
"""
from __future__ import annotations

import asyncio
import time
from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.settings import Settings
from procurve_client.auth import NoneAuth
from procurve_client.transport import ProcurveTransport

router = APIRouter(prefix="/api/v1/health", tags=["health"])

# Minimum spacing between real switch probes. The Docker HEALTHCHECK no
# longer hits this path at all; 30s matches its old interval as a worst case
# for anyone who points an external monitor at /api/v1/health.
_PROBE_TTL_SECONDS = 30.0


class HealthStatus(BaseModel):
    status: Literal["ok", "unreachable"]
    switch_reachable: bool


class LivenessStatus(BaseModel):
    status: Literal["ok"]


class HealthProbeCache:
    """Rate-limited, single-flight switch reachability probe.

    Lives on ``app.state.health_cache`` (created in the lifespan). Reuses one
    long-lived transport instead of opening a fresh TCP connection per call.
    """

    def __init__(self, ttl_seconds: float = _PROBE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._reachable: bool | None = None
        self._checked_at: float | None = None
        self._transport: ProcurveTransport | None = None

    async def reachable(self, settings: Settings) -> bool:
        # The lock both serializes probes (single-flight: concurrent callers
        # wait and then hit the fresh cache) and guards the cached fields.
        async with self._lock:
            now = time.monotonic()
            if (
                self._reachable is not None
                and self._checked_at is not None
                and now - self._checked_at < self._ttl
            ):
                return self._reachable
            self._reachable = await self._probe(settings)
            self._checked_at = time.monotonic()
            return self._reachable

    async def _probe(self, settings: Settings) -> bool:
        try:
            if self._transport is None:
                transport = ProcurveTransport(
                    host=settings.switch_host,
                    port=settings.switch_port,
                    auth=NoneAuth(),
                )
                await transport.__aenter__()
                self._transport = transport
            r = await self._transport.get("/home.html")
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — any failure maps to "unreachable"
            return False
        return r.status_code == 200

    async def aclose(self) -> None:
        if self._transport is not None:
            await self._transport.__aexit__(None, None, None)
            self._transport = None


@router.get("/live", response_model=LivenessStatus)
async def get_liveness() -> LivenessStatus:
    """Process liveness only — used by the container HEALTHCHECK.

    Deliberately switch-free: if this handler runs, the app is alive.
    """
    return LivenessStatus(status="ok")


@router.get("", response_model=HealthStatus)
async def get_health(request: Request, response: Response) -> HealthStatus:
    settings = cast(Settings, request.app.state.settings)
    cache = cast(HealthProbeCache, request.app.state.health_cache)
    reachable = await cache.reachable(settings)
    if not reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unreachable", switch_reachable=False)
    return HealthStatus(status="ok", switch_reachable=True)
