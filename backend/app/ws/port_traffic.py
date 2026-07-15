"""WebSocket endpoint that streams per-port traffic rates.

Endpoint: ``GET /ws/port-traffic``.

On connect we validate the signed ``session`` cookie the same way the HTTP
dependency does. If the session is missing, invalid, unknown, or expired we
close with ``1008 POLICY_VIOLATION`` *before* accepting — no data is emitted
to unauthenticated clients.

Switch-safety design (read-safety rule: this switch has crashed under
aggressive polling, so cadence must never scale with client count):

* ONE shared poll loop per process, owned by :class:`PortTrafficBroadcaster`
  and living on ``app.state.port_traffic``. It starts when the first
  subscriber connects, polls ``get_port_counters`` once per
  ``settings.poll_interval_seconds``, fans the computed frame out to every
  subscriber queue, and stops when the last subscriber disconnects. N open
  tabs therefore cost exactly the same switch load as one.
* The poll body is strictly sequential (fetch → fan-out → sleep), so
  requests to the switch can never stack.
* Three consecutive poll failures broadcast a close to all subscribers and
  stop the loop — a down switch is never hammered with retries; the client
  UI exposes a manual reconnect.
* Every poll tick re-validates each subscriber's session, so an expired or
  logged-out session is kicked (1008) within one interval — and a logout
  that closes the session transport can no longer blow up the poll loop:
  the broadcaster simply picks the transport of another *valid* subscriber,
  or stops when none remain.

We emit **packet rates only** because this switch firmware does not expose
byte counters — ``PortCounters`` only carries packet/mcast/bcast/error
counters (see ``procurve_client/models/port.py``).

Counters on the wire are SNMP-style 32-bit counters; they wrap at ``2**32``.
``_rate`` adds one wrap's worth of packets to any negative delta so that a
wrap looks like normal forward progress rather than a huge negative spike.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from fastapi import WebSocket, WebSocketDisconnect, status

from app import auth as auth_module
from app.auth import SESSION_COOKIE, SessionEntry, SessionStore
from app.csrf import origin_matches_host
from app.settings import Settings
from procurve_client.operations.status import get_port_counters

if TYPE_CHECKING:
    from procurve_client.models.port import PortCounters
    from procurve_client.transport import ProcurveTransport

# SNMP Counter32 wrap modulus — negative deltas get this added once.
_WRAP = 2**32

# Consecutive poll failures before the broadcaster gives up and closes all
# subscribers. Deliberately small: a down/unhappy switch must not be retried
# indefinitely (read-safety rule); the frontend offers manual reconnect.
_MAX_CONSECUTIVE_FAILURES = 3

# Per-subscriber queue depth. A slow client skips frames instead of applying
# backpressure to the shared loop (frames are point-in-time rates; dropping
# one is harmless).
_QUEUE_MAXSIZE = 8

# Sentinel pushed into subscriber queues to tell the handler to close.
_CLOSE = object()


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


class PortTrafficBroadcaster:
    """One shared switch poll loop fanned out to every WS subscriber.

    Created once in the app lifespan (``app.state.port_traffic``). The poll
    task exists only while at least one subscriber is registered, so an idle
    app sends zero traffic to the switch.
    """

    def __init__(self, *, settings: Settings, store: SessionStore) -> None:
        self._settings = settings
        self._store = store
        self._subscribers: dict[asyncio.Queue[Any], SessionEntry] = {}
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Subscription lifecycle (called from WS handlers)
    # ------------------------------------------------------------------

    def subscribe(self, entry: SessionEntry) -> asyncio.Queue[Any]:
        q: asyncio.Queue[Any] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers[q] = entry
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return q

    def unsubscribe(self, q: asyncio.Queue[Any]) -> None:
        self._subscribers.pop(q, None)
        if not self._subscribers and self._task is not None:
            self._task.cancel()
            self._task = None

    async def aclose(self) -> None:
        """Cancel the poll task on app shutdown."""
        self._subscribers.clear()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # ------------------------------------------------------------------
    # The shared poll loop
    # ------------------------------------------------------------------

    def _pick_transport(self, now: datetime) -> ProcurveTransport | None:
        """Transport of any still-valid subscriber; kicks invalid ones."""
        transport: ProcurveTransport | None = None
        for q, entry in list(self._subscribers.items()):
            if self._store.get(entry.session_id) is not entry or entry.expires_at <= now:
                self._push(q, _CLOSE)
                self._subscribers.pop(q, None)
                continue
            if transport is None:
                transport = entry.transport
        return transport

    @staticmethod
    def _push(q: asyncio.Queue[Any], item: Any) -> None:
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(item)

    def _broadcast(self, frame: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            self._push(q, frame)

    def _close_all(self) -> None:
        for q in list(self._subscribers):
            self._push(q, _CLOSE)
        self._subscribers.clear()

    async def _run(self) -> None:
        """Poll → compute rates → fan out → sleep. Never stacks requests.

        Exactly one ``auth_module._now()`` call per tick (tests pin the clock
        with finite iterators), shared by the validity check and the frame
        timestamp.
        """
        prev: dict[int, PortCounters] = {}
        prev_ts: datetime | None = None
        failures = 0
        poll_interval = self._settings.poll_interval_seconds
        while self._subscribers:
            try:
                now = auth_module._now()
                transport = self._pick_transport(now)
                if transport is None:
                    # No valid subscriber left — stop polling entirely.
                    self._close_all()
                    return
                current_list = await get_port_counters(transport)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — any switch/transport failure
                failures += 1
                structlog.get_logger().warning(
                    "port_traffic_poll_failed",
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                    consecutive_failures=failures,
                )
                if failures >= _MAX_CONSECUTIVE_FAILURES:
                    # Give up rather than hammer a struggling switch; the
                    # frontend exposes a manual reconnect.
                    structlog.get_logger().warning(
                        "port_traffic_poll_stopped",
                        reason="consecutive switch failures",
                        subscribers=len(self._subscribers),
                    )
                    self._close_all()
                    return
                await asyncio.sleep(poll_interval)
                continue
            failures = 0
            frame_ports: list[dict[str, Any]] = []
            if prev_ts is not None:
                dt = (now - prev_ts).total_seconds()
                if dt > 0:
                    for cur in current_list.ports:
                        p = prev.get(cur.port)
                        if p is None:
                            # New port appeared mid-stream; wait a tick.
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
            self._broadcast(
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
    broadcaster = cast(PortTrafficBroadcaster, app_state.port_traffic)

    # Same-origin check mirrors the HTTP write middleware (app/csrf.py): a
    # hostile same-site page must not be able to open a socket that keeps
    # the switch under poll load.
    if not origin_matches_host(
        websocket.headers.get("origin"), websocket.headers.get("host")
    ):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    entry = _lookup_session(websocket, store, settings)
    if entry is None:
        # Reject before accept — client sees a handshake failure, not a frame.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    q = broadcaster.subscribe(entry)
    try:
        while True:
            item = await q.get()
            if item is _CLOSE:
                # The broadcaster kicked us: session expired/logged out, or
                # the poll loop gave up after repeated switch failures.
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            await websocket.send_json(item)
    except WebSocketDisconnect:
        # Client hung up — normal path.
        return
    except asyncio.CancelledError:
        # Server shutdown or external cancellation — propagate so the task
        # group can tear us down cleanly.
        raise
    finally:
        broadcaster.unsubscribe(q)
        # ``close`` after close raises; suppress so we don't leak a second
        # exception during shutdown of an already-dead socket.
        with contextlib.suppress(RuntimeError):
            await websocket.close()


__all__ = ["PortTrafficBroadcaster", "port_traffic_ws"]
