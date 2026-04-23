"""Map procurve_client exceptions to HTTP responses."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from procurve_client.errors import (
    AuthError,
    OperationError,
    ProtocolError,
    TransportError,
    WriteDisabledError,
)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TransportError)
    async def _transport(request: Request, exc: TransportError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"error": "transport", "detail": str(exc)})

    @app.exception_handler(AuthError)
    async def _auth(request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

    @app.exception_handler(ProtocolError)
    async def _protocol(request: Request, exc: ProtocolError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "protocol", "detail": str(exc)})

    @app.exception_handler(OperationError)
    async def _operation(request: Request, exc: OperationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "operation", "detail": str(exc)})

    @app.exception_handler(WriteDisabledError)
    async def _write_disabled(request: Request, exc: WriteDisabledError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": "read_only", "detail": str(exc)})
