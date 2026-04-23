"""HTTP transport for the ProCurve switch."""
from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx

from procurve_client.auth import AuthStrategy, NoneAuth
from procurve_client.errors import AuthError, TransportError


class ProcurveTransport:
    """Async HTTP transport with typed error mapping and auth header injection.

    One instance per authenticated user session. Use as an async context manager.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 80,
        auth: AuthStrategy | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.host = host
        self.port = port
        self.auth: AuthStrategy = auth or NoneAuth()
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        if self.port == 80:
            return f"http://{self.host}"
        return f"http://{self.host}:{self.port}"

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "ProcurveTransport must be used as an async context manager"
            )
        return self._client

    def _auth_headers(self) -> dict[str, str]:
        return self.auth.headers()

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        client = self._require_client()
        try:
            r = await client.get(path, params=params, headers=self._auth_headers())
        except (httpx.HTTPError, OSError) as exc:
            raise TransportError(str(exc), host=self.host) from exc
        self._check_status(r)
        return r

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        client = self._require_client()
        merged_headers = {**self._auth_headers(), **(headers or {})}
        try:
            r = await client.post(
                path,
                params=params,
                data=data,
                files=files,
                content=content,
                headers=merged_headers,
            )
        except (httpx.HTTPError, OSError) as exc:
            raise TransportError(str(exc), host=self.host) from exc
        self._check_status(r)
        return r

    def _check_status(self, r: httpx.Response) -> None:
        if r.status_code in (401, 403):
            raise AuthError(f"HTTP {r.status_code} from {self.host}")
        # Other non-2xx are surfaced to the caller as httpx.Response with status_code
        # set; specific operations decide how to handle them. We do NOT raise here on
        # 4xx/5xx because some switch endpoints return 200 on logic errors with
        # diagnostic bodies instead of HTTP errors.
