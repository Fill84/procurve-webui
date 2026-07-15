"""Defense-in-depth response headers.

The SPA and API are served over plain HTTP on a trusted LAN (threat model in
docs/audit-2026-07.md), so these headers are a second layer for the day an
XSS or clickjacking vector appears — not a substitute for the Origin-check
CSRF layer in app/csrf.py. Deliberately NOT included: HSTS (dangerous on a
non-TLS deployment) and secure-cookie flags (would break plain-HTTP login).
"""
from __future__ import annotations

from fastapi import FastAPI, Request, Response

# script-src keeps 'unsafe-inline' because index.html ships a small inline
# script that applies the persisted theme before React mounts (prevents the
# flash of the wrong theme). Everything else is locked to same-origin: no
# remote scripts, styles, images, or fetch targets; no embedding.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


def install_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security_headers(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if not request.url.path.startswith("/api/"):
            # CSP matters on documents (the served SPA), not JSON bodies.
            response.headers.setdefault("Content-Security-Policy", _CSP)
        return response
