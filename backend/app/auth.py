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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
    auth = BasicAuth(username, password) if username or password else NoneAuth()
    transport = ProcurveTransport(
        host=settings.switch_host,
        port=settings.switch_port,
        auth=auth,
    )
    await transport.__aenter__()
    try:
        await _probe_credentials(transport)
    except BaseException:
        # On any failure — AuthError, TransportError, cancellation — we must
        # release the httpx client we just opened.
        await transport.__aexit__(None, None, None)
        raise
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
