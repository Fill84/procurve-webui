"""WebSocket endpoint that streams per-port traffic rates.

Endpoint: ``GET /ws/port-traffic``.

On connect we validate the signed ``session`` cookie the same way the HTTP
dependency does. If the session is missing, invalid, unknown, or expired we
close with ``1008 POLICY_VIOLATION`` *before* accepting — no data is emitted
to unauthenticated clients.

Once authenticated we poll ``get_port_counters(transport)`` every
``settings.poll_interval_seconds`` and emit one JSON frame per poll tick.
Each frame contains per-port per-second rates derived from the delta between
the current snapshot and the previous one. The first poll has no previous
snapshot so it emits an empty ``ports`` list; real rates start with frame
two.

We emit **packet rates only** because this switch firmware does not expose
byte counters — ``PortCounters`` only carries packet/mcast/bcast/error
counters (see ``procurve_client/models/port.py``). The plan's aspirational
``bytes_in_per_s`` / ``bytes_out_per_s`` fields are therefore omitted.

Counters on the wire are SNMP-style 32-bit counters; they wrap at ``2**32``.
``_rate`` adds one wrap's worth of packets to any negative delta so that a
wrap looks like normal forward progress rather than a huge negative spike.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from fastapi import WebSocket, WebSocketDisconnect, status

from app import auth as auth_module
from app.auth import SESSION_COOKIE, SessionEntry, SessionStore
from app.settings import Settings
from procurve_client.operations.status import get_port_counters
from procurve_client.transport import ProcurveTransport

if TYPE_CHECKING:
    from procurve_client.models.port import PortCounters

# SNMP Counter32 wrap modulus — negative deltas get this added once.
_WRAP = 2**32


def _rate(prev_val: int, curr_val: int, dt: float) -> float:
    """Compute ``(curr - prev) / dt`` with 32-bit counter-wrap correction."""
    delta = curr_val - prev_val
    if delta < 0:
        delta += _WRAP
    return delta / dt


def _lookup_session(
    websocket: WebSocket, store: SessionStore, settings: Settings
) -> SessionEntry | None:
    """Mirror ``app.deps.get_session`` for the WS cookie path.

    Returns the live session entry, or ``None`` if anything about the cookie
    is wrong (missing / bad signature / unknown id / expired). The caller
    must close the socket on ``None``.
    """
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    max_age = settings.session_ttl_hours * 3600
    session_id = store.unsign(token, max_age_seconds=max_age)
    if session_id is None:
        return None
    entry = store.get(session_id)
    if entry is None:
        return None
    if entry.expires_at <= auth_module._now():
        return None
    return entry


async def _run_poll_loop(
    websocket: WebSocket,
    transport: ProcurveTransport,
    poll_interval: float,
) -> None:
    """Poll counters, compute per-port rates, push one frame per interval.

    First iteration has no baseline and therefore emits ``ports=[]``. Every
    subsequent iteration emits a full list of rate entries keyed by port
    number.
    """
    prev: dict[int, PortCounters] = {}
    prev_ts: datetime | None = None
    while True:
        current_list = await get_port_counters(transport)
        now = auth_module._now()
        frame_ports: list[dict[str, Any]] = []
        if prev_ts is not None:
            dt = (now - prev_ts).total_seconds()
            if dt > 0:
                for cur in current_list.ports:
                    p = prev.get(cur.port)
                    if p is None:
                        # New port appeared mid-stream; wait for next tick.
                        continue
                    frame_ports.append(
                        {
                            "port": cur.port,
                            "pkts_in_per_s": _rate(p.pkts_rx, cur.pkts_rx, dt),
                            "pkts_out_per_s": _rate(p.pkts_tx, cur.pkts_tx, dt),
                            "mcast_in_per_s": _rate(p.mcast_rx, cur.mcast_rx, dt),
                            "mcast_out_per_s": _rate(p.mcast_tx, cur.mcast_tx, dt),
                            "bcast_in_per_s": _rate(p.bcast_rx, cur.bcast_rx, dt),
                            "bcast_out_per_s": _rate(p.bcast_tx, cur.bcast_tx, dt),
                            "errors_in_per_s": _rate(p.errors_rx, cur.errors_rx, dt),
                        }
                    )
        prev = {c.port: c for c in current_list.ports}
        prev_ts = now
        await websocket.send_json(
            {
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "poll_interval_s": poll_interval,
                "ports": frame_ports,
            }
        )
        await asyncio.sleep(poll_interval)


async def port_traffic_ws(websocket: WebSocket) -> None:
    """WebSocket handler for ``/ws/port-traffic``."""
    app_state = websocket.app.state
    settings = cast(Settings, app_state.settings)
    store = cast(SessionStore, app_state.session_store)

    entry = _lookup_session(websocket, store, settings)
    if entry is None:
        # Reject before accept — client sees a handshake failure, not a frame.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        await _run_poll_loop(
            websocket=websocket,
            transport=entry.transport,
            poll_interval=settings.poll_interval_seconds,
        )
    except WebSocketDisconnect:
        # Client hung up — normal path.
        return
    except asyncio.CancelledError:
        # Server shutdown or external cancellation — propagate so the task
        # group can tear us down cleanly.
        raise
    finally:
        # ``send_json`` after close raises; suppress so we don't leak a
        # second exception during shutdown of an already-dead socket.
        with contextlib.suppress(RuntimeError):
            await websocket.close()


__all__ = ["port_traffic_ws"]
