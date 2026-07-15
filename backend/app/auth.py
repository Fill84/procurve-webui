"""Session auth + transport cache.

Spec §11.3: the UI holds no switch credentials beyond a running login session.
We probe credentials by hitting a cheap read endpoint (`GET /home.html`); the
transport maps 401/403 to `AuthError`, which we translate to HTTP 401 at the
API layer.

Session store: an in-memory ``dict[str, SessionEntry]``. No persistence —
restart forces re-login. This is explicitly acceptable per spec.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from app.settings import Settings
from procurve_client.auth import BasicAuth, NoneAuth
from procurve_client.errors import AuthError
from procurve_client.transport import ProcurveTransport

# Cookie name shared by login/logout/whoami and the get_session dependency.
SESSION_COOKIE = "session"

# The credential probe. We deliberately pick `/home.html` (the post-login
# landing page in the switch's Java applet shell) rather than the full
# `download_config` operation because:
#   * download_config returns the full binary config on every login, which is
#     ~3 KB but costs a CPU-heavy serialize on the switch;
#   * /home.html is what the browser already hits after basic-auth succeeds;
#   * transport._check_status maps 401/403 to AuthError uniformly, so the
#     AuthError contract is identical either way.
_PROBE_PATH = "/home.html"


@dataclass
class SessionEntry:
    """One authenticated session. Holds the entered ProcurveTransport."""

    session_id: str
    username: str
    expires_at: datetime
    transport: ProcurveTransport


# ---------------------------------------------------------------------------
# Clock helper — broken out so tests can monkeypatch wall-clock time.
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Session store — in-memory dict keyed by session id.
# Lives on app.state in production; module-level default is fine for tests
# that instantiate a fresh app per case.
# ---------------------------------------------------------------------------


class SessionStore:
    """Thin wrapper around a dict, adding signing and cleanup helpers."""

    def __init__(self, secret: str) -> None:
        self._signer = TimestampSigner(secret)
        self._entries: dict[str, SessionEntry] = {}

    def sign(self, session_id: str) -> str:
        return self._signer.sign(session_id.encode()).decode()

    def unsign(self, token: str, max_age_seconds: int) -> str | None:
        try:
            raw = self._signer.unsign(token, max_age=max_age_seconds)
        except (BadSignature, SignatureExpired):
            return None
        return raw.decode()

    def put(self, entry: SessionEntry) -> None:
        self._entries[entry.session_id] = entry

    def get(self, session_id: str) -> SessionEntry | None:
        return self._entries.get(session_id)

    async def drop(self, session_id: str) -> None:
        entry = self._entries.pop(session_id, None)
        if entry is not None:
            await entry.transport.__aexit__(None, None, None)

    async def close_all(self) -> None:
        entries = list(self._entries.values())
        self._entries.clear()
        for entry in entries:
            await entry.transport.__aexit__(None, None, None)

    async def drop_expired(self, now: datetime) -> None:
        """Release entries (and their open httpx clients) past expiry.

        Called opportunistically on each login so a browser closed without
        logging out doesn't pin its transport — and the switch credentials
        held inside it — in memory until the process restarts.
        """
        expired = [
            sid for sid, entry in self._entries.items() if entry.expires_at <= now
        ]
        for sid in expired:
            await self.drop(sid)


class LoginThrottle:
    """In-memory failed-login backoff, keyed by client address.

    After ``threshold`` consecutive failures, further attempts are refused
    (the API layer returns 429) until an exponentially growing delay has
    passed; any success clears the counter. This protects the switch as much
    as the credentials: every login attempt is relayed to the fragile switch
    as a live probe, so wire-speed brute force means wire-speed switch
    hammering — the throttle rejects BEFORE any switch I/O.
    """

    def __init__(self, threshold: int = 3, max_delay_seconds: float = 30.0) -> None:
        self._threshold = threshold
        self._max_delay = max_delay_seconds
        # key -> (consecutive failures, monotonic time of the last one)
        self._failures: dict[str, tuple[int, float]] = {}

    def retry_after_seconds(self, key: str) -> float:
        entry = self._failures.get(key)
        if entry is None:
            return 0.0
        count, last = entry
        if count < self._threshold:
            return 0.0
        delay = min(2.0 ** (count - self._threshold + 1), self._max_delay)
        return max(0.0, (last + delay) - time.monotonic())

    def record_failure(self, key: str) -> None:
        count, _ = self._failures.get(key, (0, 0.0))
        self._failures[key] = (count + 1, time.monotonic())

    def record_success(self, key: str) -> None:
        self._failures.pop(key, None)


# ---------------------------------------------------------------------------
# Session creation (login path).
# ---------------------------------------------------------------------------


async def _probe_credentials(transport: ProcurveTransport) -> None:
    """Issue a cheap read; transport raises AuthError on 401/403."""
    await transport.get(_PROBE_PATH)


async def create_session(
    *,
    store: SessionStore,
    username: str,
    password: str,
    settings: Settings,
) -> SessionEntry:
    """Verify credentials against the switch and cache an entered transport."""
    # Opportunistic sweep: each login releases any expired sessions' entries
    # and transports (no periodic task needed for a single-admin tool).
    await store.drop_expired(_now())
    auth = BasicAuth(username, password) if username or password else NoneAuth()
    transport = ProcurveTransport(
        host=settings.switch_host,
        port=settings.switch_port,
        auth=auth,
    )
    log = structlog.get_logger()
    await transport.__aenter__()
    try:
        await _probe_credentials(transport)
    except BaseException as exc:
        # On any failure — AuthError, TransportError, cancellation — we must
        # release the httpx client we just opened.
        await transport.__aexit__(None, None, None)
        # Never log the password; username + failure class is the audit trail.
        log.info(
            "login_failed", username=username, reason=type(exc).__name__
        )
        raise
    log.info("login_succeeded", username=username)
    session_id = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(hours=settings.session_ttl_hours)
    entry = SessionEntry(
        session_id=session_id,
        username=username,
        expires_at=expires_at,
        transport=transport,
    )
    store.put(entry)
    return entry


__all__ = [
    "SESSION_COOKIE",
    "AuthError",
    "SessionEntry",
    "SessionStore",
    "_now",
    "create_session",
]
