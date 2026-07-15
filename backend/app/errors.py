"""Map procurve_client exceptions to HTTP responses.

Canonical wire envelope for EVERY error response:

    {"error": "<machine-readable-slug>", "detail": "<human-readable string>"}

The custom exception handlers below always produced that flat shape, but
plain ``HTTPException`` raises used to come out FastAPI-wrapped as
``{"detail": ...}`` (with `detail` being a string OR a nested dict), and
validation failures as ``{"detail": [...]}`` — three shapes no frontend
consumer actually handled, so cards rendered raw JSON at users. The
``HTTPException``/``RequestValidationError`` handlers normalize everything
to the flat envelope; the frontend's ``apiErrorMessage`` helper relies on it.
"""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from procurve_client.errors import (
    AuthError,
    OperationError,
    ProtocolError,
    TransportError,
    WriteDisabledError,
)

# Slugs for HTTPExceptions raised with a plain-string detail.
_STATUS_SLUGS = {
    400: "bad_request",
    401: "auth",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "operation",
    429: "throttled",
}


def _log_switch_error(request: Request, kind: str, exc: Exception) -> None:
    structlog.get_logger().warning(
        "switch_error",
        kind=kind,
        error=type(exc).__name__,
        detail=str(exc)[:200],
        path=request.url.path,
        method=request.method,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TransportError)
    async def _transport(request: Request, exc: TransportError) -> JSONResponse:
        _log_switch_error(request, "transport", exc)
        return JSONResponse(status_code=502, content={"error": "transport", "detail": str(exc)})

    @app.exception_handler(AuthError)
    async def _auth(request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

    @app.exception_handler(ProtocolError)
    async def _protocol(request: Request, exc: ProtocolError) -> JSONResponse:
        _log_switch_error(request, "protocol", exc)
        return JSONResponse(status_code=500, content={"error": "protocol", "detail": str(exc)})

    @app.exception_handler(OperationError)
    async def _operation(request: Request, exc: OperationError) -> JSONResponse:
        _log_switch_error(request, "operation", exc)
        return JSONResponse(status_code=422, content={"error": "operation", "detail": str(exc)})

    @app.exception_handler(WriteDisabledError)
    async def _write_disabled(request: Request, exc: WriteDisabledError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": "read_only", "detail": str(exc)})

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            # Call sites like write_safety already raise the canonical shape
            # inside `detail` — unwrap instead of double-nesting.
            content = dict(detail)
            content.setdefault("detail", "")
        else:
            content = {
                "error": _STATUS_SLUGS.get(exc.status_code, f"http_{exc.status_code}"),
                "detail": detail if isinstance(detail, str) else str(detail),
            }
        return JSONResponse(
            status_code=exc.status_code, content=content, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(x) for x in first.get("loc", ()) if x != "body")
            msg = str(first.get("msg", "invalid request"))
            human = f"{loc}: {msg}" if loc else msg
        else:
            human = "invalid request"
        return JSONResponse(
            status_code=422, content={"error": "validation", "detail": human}
        )
