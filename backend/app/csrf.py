"""Same-origin enforcement for state-changing requests.

Session auth rides a `SameSite=Strict` cookie, which blocks cross-*site*
forgery — but "site" is scheme+registrable-domain, so a page served from a
different port on the same host (e.g. a dev server on `localhost:3000` when
the UI is on `localhost:8080`) is same-site and would get the cookie
attached. This middleware closes that gap without tokens or dependencies:

* Writes (POST/PUT/DELETE/PATCH) whose `Origin` header is present and does
  not match the request `Host` are rejected with 403.
* Requests without an `Origin` header are allowed: browsers always send
  `Origin` on cross-origin (and modern ones on same-origin) fetch writes,
  while header-free requests come from non-browser clients (curl, scripts),
  which are not CSRF vectors — they hold no ambient cookie jar.

The WebSocket handshake gets the same check in `app.ws.port_traffic` (a
hostile same-site page could otherwise open a socket that triggers switch
polling).
"""
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

_WRITE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


def origin_matches_host(origin: str | None, host: str | None) -> bool:
    """True when `origin`'s host:port equals the request's Host header.

    A missing Origin passes (non-browser client); a present-but-different
    one fails. `null` origins (sandboxed iframes, data: pages) fail.
    """
    if origin is None:
        return True
    if not host:
        return False
    netloc = urlparse(origin).netloc
    if not netloc:
        return False
    # Normalize implicit default ports so http://host equals Host "host:80".
    return _strip_default_port(netloc) == _strip_default_port(host)


def _strip_default_port(netloc: str) -> str:
    return netloc.removesuffix(":80").lower()


def install_csrf_protection(app: FastAPI) -> None:
    @app.middleware("http")
    async def _same_origin_writes(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method in _WRITE_METHODS and not origin_matches_host(
            request.headers.get("origin"), request.headers.get("host")
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "csrf",
                    "detail": "cross-origin write rejected (Origin does not match Host)",
                },
            )
        response: Response = await call_next(request)
        return response
