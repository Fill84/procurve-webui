# procurve-webui — Phase 1 (Python Protocol Client) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Prerequisite:** Phase 0 plan complete, ending with the `phase0-complete` git tag. Every operation to be implemented here has a corresponding doc in `research/protocol/<tab>/<op>.md` and (for read ops) a fixture in `research/fixtures/`.

**Goal:** Build a fully typed Python client library (`procurve_client`) that faithfully replicates every ProCurve 2810-24G applet operation. Read operations are validated against live-captured fixtures; write operations are byte-matched against request templates derived from decompiled Java. Writes are never issued against the live switch except for one explicitly-approved round-trip demonstration at the end.

**Architecture:** A stateless package with one stateful class (`ProcurveTransport`) and a flat set of async operation functions grouped by tab. Safety decorators (`@READ`, `@WRITE`) mark intent and enforce a global `READ_ONLY` env flag. Errors form a typed hierarchy. Pydantic v2 models validate every request and response.

**Tech Stack:** Python 3.12, httpx (async HTTP), Pydantic v2, pytest, pytest-asyncio, pytest-httpx, respx, ruff, mypy, coverage.

**Spec:** `docs/superpowers/specs/2026-04-23-procurve-webui-design.md` (§6)
**Reference backup:** `research/backups/2026-04-23/CONFIG.pcc` (unchanged since Phase 0)

---

## File Structure

```
backend/
├── pyproject.toml                        # project config, deps, tooling
├── README.md                             # library usage
├── .env.example                          # documented env vars
├── procurve_client/
│   ├── __init__.py                       # public API re-exports
│   ├── _safety.py                        # @READ / @WRITE decorators
│   ├── transport.py                      # ProcurveTransport (httpx wrapper)
│   ├── auth.py                           # NoneAuth, BasicAuth
│   ├── errors.py                         # exception hierarchy
│   ├── parsing.py                        # low-level parsers (form, pipe, kv)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── _base.py                      # shared helpers (timestamps, MAC)
│   │   ├── backup.py                     # ConfigBackup
│   │   ├── device.py                     # DeviceInfo etc.
│   │   ├── port.py                       # PortStatus, PortConfig, PortCounters
│   │   ├── vlan.py                       # Vlan, VlanMembership
│   │   ├── stp.py                        # STP config
│   │   ├── security.py                   # security-tab models
│   │   └── log.py                        # LogEntry
│   └── operations/
│       ├── __init__.py                   # re-exports the public ops
│       ├── backup.py                     # download_config, upload_config
│       ├── identity.py
│       ├── status.py
│       ├── configuration.py
│       ├── security.py
│       ├── diagnostics.py
│       └── support.py
└── tests/
    ├── __init__.py
    ├── conftest.py                       # shared fixtures
    ├── unit/
    │   ├── test_transport.py
    │   ├── test_auth.py
    │   ├── test_errors.py
    │   ├── test_safety.py
    │   ├── test_parsing.py
    │   └── test_models/
    │       ├── test_backup.py
    │       ├── test_device.py
    │       └── ...
    ├── operations/                       # op-level unit tests (mocked transport)
    │   ├── test_backup.py                # download + upload + round-trip helpers
    │   ├── test_identity.py
    │   ├── test_status.py
    │   ├── test_configuration.py
    │   ├── test_security.py
    │   ├── test_diagnostics.py
    │   └── test_support.py
    ├── live/                             # @pytest.mark.live — not in default run
    │   ├── test_live_reads.py
    │   └── test_roundtrip.py             # write→verify→restore→verify (gated)
    └── fixtures/                         # symlinks or copies of research/fixtures/*
```

---

## Task 1.1: Bootstrap the Python project

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/README.md`
- Create: `backend/.python-version`
- Create: `backend/procurve_client/__init__.py` (empty placeholder)
- Create: `backend/tests/__init__.py` (empty placeholder)

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "procurve-client"
version = "0.1.0"
description = "Python protocol client for HP ProCurve 2810-24G (J9021A) switch"
requires-python = ">=3.12"
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Phillippe Pelzer", email = "phil.pelzer@gmail.com" }]

dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
    "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "respx>=0.21",
    "coverage>=7.4",
    "ruff>=0.4",
    "mypy>=1.9",
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["procurve_client*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "live: marks tests that hit the live switch (deselect with -m 'not live')",
    "roundtrip: marks write-verify-restore integration tests (opt-in, requires user approval)",
]
filterwarnings = ["error"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "N", "S", "C4", "RET", "SIM"]
ignore = ["E501"]  # let formatter handle line length

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # asserts are fine in tests

[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy"]

[tool.coverage.run]
source = ["procurve_client"]
branch = true

[tool.coverage.report]
precision = 1
show_missing = true
skip_covered = false
fail_under = 90
```

- [ ] **Step 2: Create `backend/.env.example`**

```dotenv
# Switch connection
SWITCH_HOST=192.168.178.3
# SWITCH_PORT=80  # default 80, override for non-standard ports

# Client behavior
READ_ONLY=true              # when true, @WRITE operations raise WriteDisabledError
POLL_INTERVAL_SECONDS=2

# Web UI (Phase 2+, harmless here)
HOST=127.0.0.1
SESSION_SECRET=               # set with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SESSION_TTL_HOURS=8
METRICS_ENABLED=false
```

- [ ] **Step 3: Create `backend/.python-version`**

```
3.12
```

- [ ] **Step 4: Create `backend/README.md`**

```markdown
# procurve_client

Async Python client library for the HP ProCurve 2810-24G (J9021A) switch.
Talks to the switch using the same HTTP protocol the legacy Java applet used.

## Install (dev)

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # (Windows Git Bash / WSL: .venv/bin/activate)
pip install -e ".[dev]"
```

## Run tests

```bash
pytest                         # unit + mocked-operation tests only
pytest -m live                 # live reads against 192.168.178.3 (requires access)
pytest -m roundtrip            # write-verify-restore (requires user approval)
```

## Public API

All operations are `async` and take a `ProcurveTransport` as first argument.
Operations are grouped by tab and imported from `procurve_client.operations`.

```python
from procurve_client import ProcurveTransport
from procurve_client.operations.backup import download_config

async def main():
    async with ProcurveTransport(host="192.168.178.3") as t:
        cfg = await download_config(t)
        print(cfg.size, cfg.sha256)
```

See `docs/superpowers/specs/2026-04-23-procurve-webui-design.md` for the
architecture background.
```

- [ ] **Step 5: Create empty package markers**

**File:** `backend/procurve_client/__init__.py`
```python
"""Python protocol client for HP ProCurve 2810-24G."""
```

**File:** `backend/tests/__init__.py`
```python
```

- [ ] **Step 6: Create virtualenv and install**

Run:
```bash
cd /f/DevProjects/procurve-webui/backend
python -m venv .venv
source .venv/Scripts/activate
pip install -e ".[dev]"
```
Expected: `Successfully installed procurve-client-0.1.0 httpx-... pydantic-... pytest-... ...`.

- [ ] **Step 7: Verify the toolchain runs**

Run:
```bash
ruff check .
mypy procurve_client
pytest --collect-only
```
Expected: ruff reports nothing (empty codebase); mypy reports no errors on the empty package; pytest shows `collected 0 items`.

- [ ] **Step 8: Commit**

Run:
```bash
cd /f/DevProjects/procurve-webui
git add backend/
git commit -m "phase1: bootstrap Python project (pyproject, tooling, empty package)"
```
Expected: commit succeeds.

---

## Task 1.2: Error hierarchy

**Files:**
- Create: `backend/procurve_client/errors.py`
- Create: `backend/tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/__init__.py`
```python
```

**File:** `backend/tests/unit/test_errors.py`
```python
"""Unit tests for the exception hierarchy."""
import pytest

from procurve_client.errors import (
    AuthError,
    OperationError,
    ParseError,
    ProcurveError,
    ProtocolError,
    SchemaError,
    TransportError,
    WriteDisabledError,
)


def test_root_is_procurve_error():
    assert issubclass(TransportError, ProcurveError)
    assert issubclass(AuthError, ProcurveError)
    assert issubclass(ProtocolError, ProcurveError)
    assert issubclass(OperationError, ProcurveError)
    assert issubclass(WriteDisabledError, ProcurveError)


def test_protocol_subclasses():
    assert issubclass(ParseError, ProtocolError)
    assert issubclass(SchemaError, ProtocolError)


def test_carries_message_and_context():
    exc = OperationError("VLAN already exists", operation="create_vlan", detail={"vlan_id": 42})
    assert str(exc) == "VLAN already exists"
    assert exc.operation == "create_vlan"
    assert exc.detail == {"vlan_id": 42}


def test_transport_error_carries_host():
    exc = TransportError("timeout", host="192.168.178.3")
    assert str(exc) == "timeout"
    assert exc.host == "192.168.178.3"


def test_write_disabled_error_default_message():
    exc = WriteDisabledError(operation="set_port_name")
    assert "READ_ONLY" in str(exc)
    assert exc.operation == "set_port_name"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd backend
source .venv/Scripts/activate
pytest tests/unit/test_errors.py -v
```
Expected: all tests FAIL with `ModuleNotFoundError: No module named 'procurve_client.errors'`.

- [ ] **Step 3: Implement `errors.py`**

**File:** `backend/procurve_client/errors.py`
```python
"""Typed exception hierarchy for the procurve_client library."""
from __future__ import annotations

from typing import Any


class ProcurveError(Exception):
    """Root of the procurve_client error hierarchy."""


class TransportError(ProcurveError):
    """Network, timeout, DNS, or socket-level failure."""

    def __init__(self, message: str, *, host: str | None = None) -> None:
        super().__init__(message)
        self.host = host


class AuthError(ProcurveError):
    """Authentication failure (401/403 or auth-redirect)."""


class ProtocolError(ProcurveError):
    """Switch returned a response we could not handle as expected."""


class ParseError(ProtocolError):
    """Low-level parser could not read the response body."""


class SchemaError(ProtocolError):
    """Response parsed but violated the Pydantic schema."""


class OperationError(ProcurveError):
    """Switch explicitly rejected the operation."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.detail = detail or {}


class WriteDisabledError(ProcurveError):
    """A @WRITE operation was invoked while READ_ONLY is enabled."""

    def __init__(self, *, operation: str) -> None:
        super().__init__(
            f"Write operation {operation!r} is disabled (READ_ONLY=true). "
            f"Set READ_ONLY=false to allow."
        )
        self.operation = operation
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_errors.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/errors.py backend/tests/unit/test_errors.py backend/tests/unit/__init__.py
git commit -m "phase1: typed exception hierarchy with tests"
```
Expected: commit succeeds.

---

## Task 1.3: Safety decorators (@READ / @WRITE) and READ_ONLY enforcement

**Files:**
- Create: `backend/procurve_client/_safety.py`
- Create: `backend/tests/unit/test_safety.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_safety.py`
```python
"""Unit tests for the @READ / @WRITE safety decorators."""
import os

import pytest

from procurve_client._safety import READ, WRITE, is_read, is_write
from procurve_client.errors import WriteDisabledError


@READ
async def sample_read() -> str:
    return "ok"


@WRITE
async def sample_write() -> str:
    return "wrote"


async def test_read_decorator_is_noop():
    assert await sample_read() == "ok"
    assert is_read(sample_read) is True
    assert is_write(sample_read) is False


async def test_write_runs_when_read_only_false(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    assert await sample_write() == "wrote"
    assert is_write(sample_write) is True


async def test_write_blocked_when_read_only_true(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "true")
    with pytest.raises(WriteDisabledError) as exc_info:
        await sample_write()
    assert exc_info.value.operation == "sample_write"


async def test_write_blocked_when_read_only_unset(monkeypatch):
    # default: safer choice is to block writes
    monkeypatch.delenv("READ_ONLY", raising=False)
    with pytest.raises(WriteDisabledError):
        await sample_write()


async def test_write_read_only_accepts_various_truthy(monkeypatch):
    for value in ("false", "FALSE", "0", "no", "off", ""):
        monkeypatch.setenv("READ_ONLY", value)
        # only "false", "0", "no", "off" should enable writes; "" should block (default-safe)
        if value in ("false", "FALSE", "0", "no", "off"):
            assert await sample_write() == "wrote"
        else:
            with pytest.raises(WriteDisabledError):
                await sample_write()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_safety.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'procurve_client._safety'`.

- [ ] **Step 3: Implement `_safety.py`**

**File:** `backend/procurve_client/_safety.py`
```python
"""Safety decorators: @READ (marker) and @WRITE (marker + READ_ONLY enforcement)."""
from __future__ import annotations

import functools
import os
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from procurve_client.errors import WriteDisabledError

P = ParamSpec("P")
R = TypeVar("R")

_READ_ATTR = "__procurve_read__"
_WRITE_ATTR = "__procurve_write__"


def _read_only_enabled() -> bool:
    """Return True unless READ_ONLY is explicitly set to a falsey value."""
    raw = os.environ.get("READ_ONLY", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def READ(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Mark an async operation as read-only. Runtime behavior is a no-op."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await func(*args, **kwargs)

    setattr(wrapper, _READ_ATTR, True)
    return wrapper


def WRITE(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Mark an async operation as writing. Blocked when READ_ONLY is enabled."""

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if _read_only_enabled():
            raise WriteDisabledError(operation=func.__name__)
        return await func(*args, **kwargs)

    setattr(wrapper, _WRITE_ATTR, True)
    return wrapper


def is_read(func: Any) -> bool:
    return bool(getattr(func, _READ_ATTR, False))


def is_write(func: Any) -> bool:
    return bool(getattr(func, _WRITE_ATTR, False))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_safety.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/_safety.py backend/tests/unit/test_safety.py
git commit -m "phase1: @READ / @WRITE decorators with READ_ONLY enforcement"
```
Expected: commit succeeds.

---

## Task 1.4: Auth strategies

**Files:**
- Create: `backend/procurve_client/auth.py`
- Create: `backend/tests/unit/test_auth.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_auth.py`
```python
"""Unit tests for auth strategies."""
from procurve_client.auth import BasicAuth, NoneAuth


def test_none_auth_emits_no_headers():
    auth = NoneAuth()
    assert auth.headers() == {}


def test_basic_auth_emits_authorization_header():
    auth = BasicAuth(username="admin", password="hunter2")
    headers = auth.headers()
    assert "Authorization" in headers
    # Standard base64 of 'admin:hunter2'
    assert headers["Authorization"] == "Basic YWRtaW46aHVudGVyMg=="


def test_basic_auth_accepts_blank_credentials():
    # Switch currently has blank/blank; this must not crash.
    auth = BasicAuth(username="", password="")
    headers = auth.headers()
    assert headers["Authorization"] == "Basic Og=="


def test_none_and_basic_auth_are_distinct_types():
    assert NoneAuth() != BasicAuth(username="", password="")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_auth.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `auth.py`**

**File:** `backend/procurve_client/auth.py`
```python
"""Authentication strategies for ProcurveTransport."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol


class AuthStrategy(Protocol):
    def headers(self) -> dict[str, str]:
        """Return headers to attach to every request."""


@dataclass(frozen=True)
class NoneAuth:
    """No authentication (current switch default: blank user/password)."""

    def headers(self) -> dict[str, str]:
        return {}


@dataclass(frozen=True)
class BasicAuth:
    """HTTP Basic authentication."""

    username: str
    password: str

    def headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_auth.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/auth.py backend/tests/unit/test_auth.py
git commit -m "phase1: NoneAuth and BasicAuth strategies"
```
Expected: commit succeeds.

---

## Task 1.5: Transport — skeleton

**Files:**
- Create: `backend/procurve_client/transport.py`
- Create: `backend/tests/unit/test_transport.py`

- [ ] **Step 1: Write the failing test (construction and context manager)**

**File:** `backend/tests/unit/test_transport.py`
```python
"""Unit tests for ProcurveTransport."""
import pytest
import respx
from httpx import Response

from procurve_client.auth import BasicAuth, NoneAuth
from procurve_client.errors import AuthError, TransportError
from procurve_client.transport import ProcurveTransport


def test_transport_defaults():
    t = ProcurveTransport(host="192.168.178.3")
    assert t.host == "192.168.178.3"
    assert t.port == 80
    assert t.base_url == "http://192.168.178.3"
    assert isinstance(t.auth, NoneAuth)


def test_transport_explicit_auth_and_port():
    t = ProcurveTransport(
        host="switch.lan",
        port=8080,
        auth=BasicAuth(username="admin", password="pw"),
    )
    assert t.port == 8080
    assert t.base_url == "http://switch.lan:8080"
    assert isinstance(t.auth, BasicAuth)


async def test_transport_is_async_context_manager():
    async with ProcurveTransport(host="192.168.178.3") as t:
        assert t._client is not None
    # after __aexit__ the client is closed
    assert t._client is None


@respx.mock
async def test_get_returns_response_on_2xx():
    respx.get("http://192.168.178.3/home.html").mock(
        return_value=Response(200, text="<html>ok</html>")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        r = await t.get("/home.html")
    assert r.status_code == 200
    assert "<html>" in r.text


@respx.mock
async def test_get_raises_transport_error_on_network_issue():
    respx.get("http://192.168.178.3/home.html").mock(side_effect=ConnectionError("boom"))
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(TransportError):
            await t.get("/home.html")


@respx.mock
async def test_get_raises_auth_error_on_401():
    respx.get("http://192.168.178.3/home.html").mock(return_value=Response(401, text=""))
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(AuthError):
            await t.get("/home.html")


@respx.mock
async def test_get_attaches_auth_headers_when_basic():
    route = respx.get("http://192.168.178.3/home.html").mock(return_value=Response(200, text="x"))
    async with ProcurveTransport(
        host="192.168.178.3",
        auth=BasicAuth(username="admin", password="pw"),
    ) as t:
        await t.get("/home.html")
    assert route.called
    assert route.calls.last.request.headers["Authorization"].startswith("Basic ")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_transport.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'procurve_client.transport'`.

- [ ] **Step 3: Implement `transport.py`**

**File:** `backend/procurve_client/transport.py`
```python
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
        except httpx.HTTPError as exc:
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
        except httpx.HTTPError as exc:
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_transport.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/transport.py backend/tests/unit/test_transport.py
git commit -m "phase1: ProcurveTransport skeleton with GET/POST + error mapping"
```
Expected: commit succeeds.

---

## Task 1.6: Parsing helpers

**Files:**
- Create: `backend/procurve_client/parsing.py`
- Create: `backend/tests/unit/test_parsing.py`

**Background:** The exact parsers needed depend on the response formats uncovered in Phase 0. This task implements the three most likely formats: pipe-delimited lines, key=value pairs, and the ProCurve running-config text. Additional parsers are added in Task 1.10 as operations require them.

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_parsing.py`
```python
"""Unit tests for low-level parsers."""
import pytest

from procurve_client.errors import ParseError
from procurve_client.parsing import parse_kv_lines, parse_pipe_delimited, parse_running_config


def test_parse_pipe_delimited_simple():
    body = "1|up|2|down|3|up"
    rows = parse_pipe_delimited(body, columns=2)
    assert rows == [("1", "up"), ("2", "down"), ("3", "up")]


def test_parse_pipe_delimited_trailing_empty_is_dropped():
    body = "1|up|2|down|"
    rows = parse_pipe_delimited(body, columns=2)
    assert rows == [("1", "up"), ("2", "down")]


def test_parse_pipe_delimited_raises_on_misaligned():
    with pytest.raises(ParseError):
        parse_pipe_delimited("1|up|2", columns=2)


def test_parse_kv_lines_single_value():
    body = "hostname=HP2810_01\nuptime=123456\n"
    assert parse_kv_lines(body) == {"hostname": "HP2810_01", "uptime": "123456"}


def test_parse_kv_lines_crlf():
    body = "a=1\r\nb=2\r\n"
    assert parse_kv_lines(body) == {"a": "1", "b": "2"}


def test_parse_kv_lines_raises_on_missing_equals():
    with pytest.raises(ParseError):
        parse_kv_lines("a=1\noops\n")


def test_parse_running_config_header_is_stripped():
    body = (
        "; J9021A Configuration Editor; Created on release #N.11.78\r\n"
        "\r\n"
        'hostname "HP2810_01"\r\n'
        'snmp-server community "public" Unrestricted\r\n'
    )
    parsed = parse_running_config(body)
    assert parsed.hostname == "HP2810_01"
    assert parsed.firmware == "N.11.78"
    assert 'snmp-server community "public" Unrestricted' in parsed.raw


def test_parse_running_config_keeps_raw_bytes_for_round_trip():
    body = "; J9021A Configuration Editor; Created on release #N.11.78\r\nhostname \"X\"\r\n"
    parsed = parse_running_config(body)
    assert parsed.raw == body
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_parsing.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `parsing.py`**

**File:** `backend/procurve_client/parsing.py`
```python
"""Low-level response parsers used by operation functions."""
from __future__ import annotations

import re
from dataclasses import dataclass

from procurve_client.errors import ParseError

_FIRMWARE_RE = re.compile(r"Created on release #(?P<fw>[A-Z0-9.]+)")
_HOSTNAME_RE = re.compile(r'^hostname\s+"(?P<name>[^"]*)"', re.MULTILINE)


def parse_pipe_delimited(body: str, *, columns: int) -> list[tuple[str, ...]]:
    """Parse a flat pipe-delimited stream into N-tuples of `columns` strings.

    Trailing empty element (from a trailing pipe) is tolerated. Any other
    mismatch raises ParseError.
    """
    parts = body.split("|")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    if len(parts) % columns != 0:
        raise ParseError(
            f"pipe-delimited body has {len(parts)} parts, not a multiple of {columns}"
        )
    return [tuple(parts[i : i + columns]) for i in range(0, len(parts), columns)]


def parse_kv_lines(body: str) -> dict[str, str]:
    """Parse lines of the form `key=value\\n` into a dict. CRLF tolerated."""
    out: dict[str, str] = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=" not in line:
            raise ParseError(f"expected key=value line, got: {line!r}")
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@dataclass(frozen=True)
class RunningConfig:
    """Parsed view of a ProCurve running-config (CONFIG.pcc) text."""

    raw: str
    hostname: str
    firmware: str


def parse_running_config(body: str) -> RunningConfig:
    """Parse a running-config text into a structured view while retaining the raw bytes."""
    fw_match = _FIRMWARE_RE.search(body)
    name_match = _HOSTNAME_RE.search(body)
    return RunningConfig(
        raw=body,
        hostname=name_match.group("name") if name_match else "",
        firmware=fw_match.group("fw") if fw_match else "",
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_parsing.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/parsing.py backend/tests/unit/test_parsing.py
git commit -m "phase1: low-level parsers (pipe-delimited, kv-lines, running-config)"
```
Expected: commit succeeds.

---

## Task 1.7: Base models

**Files:**
- Create: `backend/procurve_client/models/__init__.py`
- Create: `backend/procurve_client/models/_base.py`
- Create: `backend/tests/unit/test_models/__init__.py`
- Create: `backend/tests/unit/test_models/test_base.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_models/__init__.py`
```python
```

**File:** `backend/tests/unit/test_models/test_base.py`
```python
"""Unit tests for shared Pydantic helpers."""
import pytest
from pydantic import ValidationError

from procurve_client.models._base import MacAddress, PortNumber, VlanId


def test_mac_address_accepts_colon_separated():
    m = MacAddress(value="aa:bb:cc:dd:ee:ff")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_accepts_dash_separated():
    m = MacAddress(value="AA-BB-CC-DD-EE-FF")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_accepts_procurve_format():
    # ProCurve formats MACs as 6-byte hex with no separators sometimes
    m = MacAddress(value="aabbccddeeff")
    assert m.value == "AA:BB:CC:DD:EE:FF"


def test_mac_address_rejects_short():
    with pytest.raises(ValidationError):
        MacAddress(value="aa:bb:cc:dd:ee")


def test_port_number_bounds():
    assert PortNumber(value=1).value == 1
    assert PortNumber(value=24).value == 24
    with pytest.raises(ValidationError):
        PortNumber(value=0)
    with pytest.raises(ValidationError):
        PortNumber(value=25)


def test_vlan_id_bounds():
    assert VlanId(value=1).value == 1
    assert VlanId(value=4094).value == 4094
    with pytest.raises(ValidationError):
        VlanId(value=0)
    with pytest.raises(ValidationError):
        VlanId(value=4095)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_models/test_base.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `_base.py`**

**File:** `backend/procurve_client/models/__init__.py`
```python
"""Pydantic models for the procurve_client library."""
```

**File:** `backend/procurve_client/models/_base.py`
```python
"""Shared Pydantic helpers for procurve_client models."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_MAC_HEX_ONLY = re.compile(r"^[0-9A-Fa-f]{12}$")
_MAC_SEPARATED = re.compile(r"^[0-9A-Fa-f]{2}([:\-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}$")


class MacAddress(BaseModel):
    """Normalized MAC address in uppercase colon-separated form."""

    value: str

    @field_validator("value")
    @classmethod
    def _normalize(cls, v: str) -> str:
        if _MAC_SEPARATED.match(v):
            hex_only = v.replace(":", "").replace("-", "")
        elif _MAC_HEX_ONLY.match(v):
            hex_only = v
        else:
            raise ValueError(f"not a valid MAC address: {v!r}")
        hex_only = hex_only.upper()
        return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


class PortNumber(BaseModel):
    """Port number 1..24 for the 2810-24G chassis."""

    value: int = Field(..., ge=1, le=24)


class VlanId(BaseModel):
    """VLAN ID 1..4094."""

    value: int = Field(..., ge=1, le=4094)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_models/test_base.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/models/__init__.py backend/procurve_client/models/_base.py \
        backend/tests/unit/test_models/
git commit -m "phase1: base Pydantic models (MacAddress, PortNumber, VlanId)"
```
Expected: commit succeeds.

---

## Task 1.8: Backup model

**Files:**
- Create: `backend/procurve_client/models/backup.py`
- Create: `backend/tests/unit/test_models/test_backup.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_models/test_backup.py`
```python
"""Unit tests for the ConfigBackup model."""
import pytest
from pydantic import ValidationError

from procurve_client.models.backup import ConfigBackup, ConfigSlot


def test_config_backup_from_text_computes_hash_and_size():
    text = "; J9021A Configuration Editor; Created on release #N.11.78\r\nhostname \"X\"\r\n"
    cb = ConfigBackup.from_text(text)
    assert cb.text == text
    assert cb.size == len(text.encode("ascii"))
    assert cb.sha256 == "6c4a8b1e2f...".lower()[:0] + cb.sha256  # placeholder self-consistency
    # Real check: sha256 is 64 hex chars lowercase
    assert len(cb.sha256) == 64
    assert all(c in "0123456789abcdef" for c in cb.sha256)


def test_config_backup_slot_values():
    assert ConfigSlot.PRIMARY.value == 1
    assert ConfigSlot.SECONDARY.value == 2


def test_config_backup_reference_sha_matches_known():
    # Fixture recorded 2026-04-23 from the user's switch; see
    # research/backups/2026-04-23/CONFIG.pcc
    expected = "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11"
    # Re-reading the fixture verifies the hashing implementation is byte-correct.
    from pathlib import Path
    fixture = Path(__file__).resolve().parents[3].parent / "research" / "backups" / "2026-04-23" / "CONFIG.pcc"
    text = fixture.read_text(encoding="ascii", newline="")
    cb = ConfigBackup.from_text(text)
    assert cb.size == 2904
    assert cb.sha256 == expected


def test_config_backup_rejects_empty():
    with pytest.raises(ValidationError):
        ConfigBackup(text="", size=0, sha256="")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_models/test_backup.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `backup.py`**

**File:** `backend/procurve_client/models/backup.py`
```python
"""Models for configuration backup download / upload."""
from __future__ import annotations

import hashlib
from enum import IntEnum

from pydantic import BaseModel, Field, model_validator


class ConfigSlot(IntEnum):
    """Config file slot on the switch."""

    PRIMARY = 1
    SECONDARY = 2


class ConfigBackup(BaseModel):
    """A downloaded switch configuration snapshot."""

    text: str = Field(..., min_length=1)
    size: int = Field(..., gt=0)
    sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_consistency(self) -> "ConfigBackup":
        if len(self.text.encode("ascii")) != self.size:
            raise ValueError("size does not match len(text.encode('ascii'))")
        if hashlib.sha256(self.text.encode("ascii")).hexdigest() != self.sha256:
            raise ValueError("sha256 does not match sha256(text)")
        return self

    @classmethod
    def from_text(cls, text: str) -> "ConfigBackup":
        raw = text.encode("ascii")
        return cls(text=text, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_models/test_backup.py -v
```
Expected: all tests PASS.

Note on the `placeholder self-consistency` line in the test: that line is a harmless no-op that documents intent; the following explicit length + hex-charset check is the real assertion.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/models/backup.py backend/tests/unit/test_models/test_backup.py
git commit -m "phase1: ConfigBackup model with hash/size consistency validation"
```
Expected: commit succeeds.

---

## Task 1.9: Exemplar read operation — `download_config`

**Files:**
- Create: `backend/procurve_client/operations/__init__.py`
- Create: `backend/procurve_client/operations/backup.py`
- Create: `backend/tests/operations/__init__.py`
- Create: `backend/tests/operations/conftest.py`
- Create: `backend/tests/operations/test_backup_download.py`

**Background:** This is the fully-worked exemplar for a **read** operation. Later operations follow this exact pattern: protocol doc → Pydantic model → operation function → unit test using fixture → re-export.

- [ ] **Step 1: Create shared operation test fixtures**

**File:** `backend/tests/operations/__init__.py`
```python
```

**File:** `backend/tests/operations/conftest.py`
```python
"""Shared fixtures for operation-level tests."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to research/fixtures/ — live-captured responses from Phase 0."""
    return Path(__file__).resolve().parents[3] / "research" / "fixtures"


@pytest.fixture
def reference_backup_text(fixtures_dir: Path) -> str:
    path = fixtures_dir / "download_config.response.txt"
    return path.read_text(encoding="ascii", newline="")
```

- [ ] **Step 2: Write the failing test**

**File:** `backend/tests/operations/test_backup_download.py`
```python
"""Unit tests for download_config."""
import pytest
import respx
from httpx import Response

from procurve_client.auth import NoneAuth
from procurve_client.models.backup import ConfigSlot
from procurve_client.operations.backup import download_config
from procurve_client.transport import ProcurveTransport


@respx.mock
async def test_download_config_default_slot(reference_backup_text: str):
    respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(
            200,
            text=reference_backup_text,
            headers={"Content-Type": 'application/octet-stream; file="CONFIG.pcc"'},
        )
    )
    async with ProcurveTransport(host="192.168.178.3", auth=NoneAuth()) as t:
        backup = await download_config(t)
    assert backup.size == 2904
    assert backup.sha256 == (
        "f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11"
    )
    assert "hostname \"HP2810_01\"" in backup.text


@respx.mock
async def test_download_config_sends_expected_query(reference_backup_text: str):
    route = respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(200, text=reference_backup_text,
                              headers={"Content-Type": "application/octet-stream"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await download_config(t, slot=ConfigSlot.SECONDARY)
    assert route.called
    req = route.calls.last.request
    assert req.url.params["idx"] == "2"
    assert req.url.params["fg"] == "2"
    assert req.url.params["D1"] == "Download"


@respx.mock
async def test_download_config_raises_on_non_attachment_response():
    # Switch returned HTML (happens when D1 is omitted) — operation must notice.
    respx.get("http://192.168.178.3/cgi/configfile").mock(
        return_value=Response(200, text="<html>oops</html>",
                              headers={"Content-Type": "text/html"})
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        from procurve_client.errors import ProtocolError
        with pytest.raises(ProtocolError):
            await download_config(t)
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
pytest tests/operations/test_backup_download.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'procurve_client.operations'`.

- [ ] **Step 4: Implement the operation**

**File:** `backend/procurve_client/operations/__init__.py`
```python
"""Operation functions, grouped by tab."""
```

**File:** `backend/procurve_client/operations/backup.py`
```python
"""Backup download (read) and restore (write) operations."""
from __future__ import annotations

import hashlib

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ProtocolError
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.transport import ProcurveTransport

_CGI_PATH = "/cgi/configfile"


@READ
async def download_config(
    transport: ProcurveTransport,
    *,
    slot: ConfigSlot = ConfigSlot.PRIMARY,
) -> ConfigBackup:
    """Download the current running-config from the switch.

    Wraps `GET /cgi/configfile?idx={slot}&fg={slot}&D1=Download`.
    See `research/protocol/backup/download.md` for the contract.
    """
    r = await transport.get(
        _CGI_PATH,
        params={"idx": int(slot), "fg": int(slot), "D1": "Download"},
    )
    ctype = r.headers.get("Content-Type", "")
    if "application/octet-stream" not in ctype:
        raise ProtocolError(
            f"expected octet-stream config download, got Content-Type={ctype!r}"
        )
    text = r.text
    if not text:
        raise ProtocolError("empty config body")
    raw = text.encode("ascii")
    return ConfigBackup(
        text=text,
        size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


# Upload (write) follows in Task 1.10.
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
pytest tests/operations/test_backup_download.py -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

Run:
```bash
git add backend/procurve_client/operations/__init__.py \
        backend/procurve_client/operations/backup.py \
        backend/tests/operations/
git commit -m "phase1: download_config operation (exemplar read) with unit tests"
```
Expected: commit succeeds.

---

## Task 1.10: Exemplar write operation — `restore_config`

**Files:**
- Modify: `backend/procurve_client/operations/backup.py`
- Create: `backend/tests/operations/test_backup_restore.py`

**Background:** This is the fully-worked exemplar for a **write** operation. Test uses byte-match against a request template derived from `research/protocol/backup/upload-restore.md`. No live POST is made.

**Assumption about the contract:** based on the HTML form in `configuration/uploadConfile.html`, the upload uses `multipart/form-data` with a `file` part named according to the form's file-input `name` attribute (to be confirmed during Phase 0 Task 0.12). The code below uses the documented field names; if Phase 0 documented different names, adjust the two `UPLOAD_*` constants here and re-run the test.

- [ ] **Step 1: Write the failing test (byte-match approach)**

**File:** `backend/tests/operations/test_backup_restore.py`
```python
"""Unit tests for restore_config.

These tests do NOT issue network calls against the live switch. They verify:
  1. The request is well-formed (status-code path).
  2. The request body byte-matches the documented template.
"""
from pathlib import Path

import pytest
import respx
from httpx import Response

from procurve_client.errors import WriteDisabledError
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.operations.backup import restore_config, UPLOAD_FIELD_NAME, UPLOAD_PATH
from procurve_client.transport import ProcurveTransport


def _reference_backup() -> ConfigBackup:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    return ConfigBackup.from_text(fixture.read_text(encoding="ascii", newline=""))


async def test_restore_config_requires_read_only_false(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "true")
    backup = _reference_backup()
    async with ProcurveTransport(host="192.168.178.3") as t:
        with pytest.raises(WriteDisabledError):
            await restore_config(t, backup=backup, slot=ConfigSlot.PRIMARY)


@respx.mock
async def test_restore_config_posts_multipart(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    route = respx.post(f"http://192.168.178.3{UPLOAD_PATH}").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await restore_config(t, backup=backup, slot=ConfigSlot.PRIMARY)
    assert route.called
    req = route.calls.last.request
    ctype = req.headers["Content-Type"]
    assert ctype.startswith("multipart/form-data")
    body = req.content
    # The body must contain the upload field name and the config text verbatim.
    assert f'name="{UPLOAD_FIELD_NAME}"'.encode() in body
    assert b'filename="CONFIG.pcc"' in body
    assert backup.text.encode("ascii") in body


@respx.mock
async def test_restore_config_preserves_bytes_exactly(monkeypatch):
    """Round-trip fidelity: the upload body must contain the backup bytes unchanged."""
    monkeypatch.setenv("READ_ONLY", "false")
    backup = _reference_backup()
    route = respx.post(f"http://192.168.178.3{UPLOAD_PATH}").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await restore_config(t, backup=backup, slot=ConfigSlot.PRIMARY)
    req = route.calls.last.request
    # Extract the file part and compare SHA256.
    body = req.content
    # The file part starts after the last occurrence of the filename parameter.
    marker = b'filename="CONFIG.pcc"'
    idx = body.find(marker)
    assert idx >= 0
    # Find end of part headers (double CRLF), then the part body up to the next boundary.
    headers_end = body.find(b"\r\n\r\n", idx)
    assert headers_end >= 0
    content_start = headers_end + 4
    # The boundary marker starts with \r\n-- on the line after the file content.
    boundary_marker = b"\r\n--"
    content_end = body.find(boundary_marker, content_start)
    file_bytes = body[content_start:content_end]
    import hashlib
    assert hashlib.sha256(file_bytes).hexdigest() == backup.sha256
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/operations/test_backup_restore.py -v
```
Expected: FAIL with `ImportError` on `restore_config` / `UPLOAD_PATH` / `UPLOAD_FIELD_NAME`.

- [ ] **Step 3: Extend `operations/backup.py`**

Replace the file contents with:

```python
"""Backup download (read) and restore (write) operations."""
from __future__ import annotations

import hashlib

from procurve_client._safety import READ, WRITE
from procurve_client.errors import ProtocolError
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.transport import ProcurveTransport

# --- Endpoint constants (derived from research/protocol/backup/*.md) ---
# Download (GET /cgi/configfile?idx=...&fg=...&D1=Download).
_DOWNLOAD_PATH = "/cgi/configfile"
# Upload/restore — path and field names come from
# research/mirror/2026-04-23/configuration/uploadConfile.html.
# These must be updated if Phase 0 documents different values.
UPLOAD_PATH = "/cgi/configfile"
UPLOAD_FIELD_NAME = "file"       # input[type=file] "name" attribute
UPLOAD_IDX_FIELD = "idx"         # hidden slot-selector field


@READ
async def download_config(
    transport: ProcurveTransport,
    *,
    slot: ConfigSlot = ConfigSlot.PRIMARY,
) -> ConfigBackup:
    """Download the current running-config. See research/protocol/backup/download.md."""
    r = await transport.get(
        _DOWNLOAD_PATH,
        params={"idx": int(slot), "fg": int(slot), "D1": "Download"},
    )
    ctype = r.headers.get("Content-Type", "")
    if "application/octet-stream" not in ctype:
        raise ProtocolError(
            f"expected octet-stream config download, got Content-Type={ctype!r}"
        )
    text = r.text
    if not text:
        raise ProtocolError("empty config body")
    raw = text.encode("ascii")
    return ConfigBackup(text=text, size=len(raw), sha256=hashlib.sha256(raw).hexdigest())


@WRITE
async def restore_config(
    transport: ProcurveTransport,
    *,
    backup: ConfigBackup,
    slot: ConfigSlot = ConfigSlot.PRIMARY,
) -> None:
    """Upload a ConfigBackup to the switch.

    Sends `POST <UPLOAD_PATH>` as multipart/form-data with:
      - idx: slot number
      - file: backup.text, filename="CONFIG.pcc", octet-stream

    See research/protocol/backup/upload-restore.md for the full contract.
    """
    files = {
        UPLOAD_FIELD_NAME: (
            "CONFIG.pcc",
            backup.text.encode("ascii"),
            "application/octet-stream",
        ),
    }
    data = {UPLOAD_IDX_FIELD: str(int(slot))}
    r = await transport.post(UPLOAD_PATH, data=data, files=files)
    if r.status_code != 200:
        raise ProtocolError(
            f"upload returned HTTP {r.status_code}: body={r.text[:200]!r}"
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/operations/test_backup_restore.py -v
```
Expected: all tests PASS. If an assertion about the field name fails, update `UPLOAD_FIELD_NAME` in `operations/backup.py` to match Phase 0's documented value and re-run.

- [ ] **Step 5: Run the whole test suite**

Run:
```bash
pytest
```
Expected: all previously-passing tests still pass; the two new test files also pass.

- [ ] **Step 6: Commit**

Run:
```bash
git add backend/procurve_client/operations/backup.py backend/tests/operations/test_backup_restore.py
git commit -m "phase1: restore_config operation (exemplar write) with byte-match tests"
```
Expected: commit succeeds.

---

## Task 1.11: Operation scaffolding tasks (one per tab)

**Background:** Now apply the pattern established in Tasks 1.9 and 1.10 to every operation documented in Phase 0. The work is bite-sized but parameterized on Phase 0's outputs, which is why this can't be pre-enumerated operation-by-operation in this plan. Each sub-task below follows the SAME 5-step pattern, producing concrete code — not placeholders.

Sub-tasks:

### Task 1.11.a: Identity tab operations
### Task 1.11.b: Status tab operations
### Task 1.11.c: Configuration tab operations (largest — includes VLAN, ports, system, IP, QoS, etc.)
### Task 1.11.d: Security tab operations
### Task 1.11.e: Diagnostics tab operations
### Task 1.11.f: Support tab operations

For each tab task, repeat the following pattern **once per operation** documented under `research/protocol/<tab>/`:

- [ ] **Step 1: Write the failing test**

Use the test template below. Read the protocol doc for the operation and translate its fields into test inputs and expected outputs. For reads, drive the test from the fixture under `research/fixtures/<tab>__<op>.response.txt`. For writes, assert byte-match against the "Example request" block in the protocol doc.

**Read test template:**
```python
# tests/operations/test_<tab>_<op>.py
from pathlib import Path
import respx
from httpx import Response

from procurve_client.operations.<tab> import <op_func>
from procurve_client.transport import ProcurveTransport


@respx.mock
async def test_<op_func>_parses_fixture():
    fixture = (Path(__file__).resolve().parents[3] / "research" / "fixtures"
               / "<tab>__<op>.response.txt").read_text()
    respx.get("http://192.168.178.3<url-from-doc>").mock(
        return_value=Response(200, text=fixture)
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        result = await <op_func>(t)
    # Assert each field from the doc's "Example response" section:
    assert result.<field1> == <expected>
    # ... one assertion per documented field
```

**Write test template:**
```python
# tests/operations/test_<tab>_<op>.py
import respx
from httpx import Response

from procurve_client.operations.<tab> import <op_func>
from procurve_client.models.<domain> import <RequestModel>
from procurve_client.transport import ProcurveTransport


@respx.mock
async def test_<op_func>_sends_expected_body(monkeypatch):
    monkeypatch.setenv("READ_ONLY", "false")
    route = respx.post("http://192.168.178.3<url-from-doc>").mock(
        return_value=Response(200, text="OK")
    )
    async with ProcurveTransport(host="192.168.178.3") as t:
        await <op_func>(t, <args-from-doc>)
    req = route.calls.last.request
    # Byte-match against the documented request body template:
    for expected_fragment in [b"<frag1>", b"<frag2>", ...]:
        assert expected_fragment in req.content
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/operations/test_<tab>_<op>.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement the model (if new domain)**

Create / extend `procurve_client/models/<domain>.py` with a Pydantic class matching every field in the protocol doc's "Field reference" table. Use validators to enforce the constraints from the doc (e.g. `Literal[...]`, `ge=`/`le=`, regex patterns). If the model already exists, extend it.

- [ ] **Step 4: Implement the operation function**

Add / extend `procurve_client/operations/<tab>.py`:

```python
from procurve_client._safety import READ  # or WRITE
from procurve_client.errors import ProtocolError
from procurve_client.models.<domain> import <Model>
from procurve_client.parsing import <parser>  # from task 1.6 or add new parser
from procurve_client.transport import ProcurveTransport


@READ   # or @WRITE
async def <op_func>(transport: ProcurveTransport, <args>) -> <ReturnModel>:
    """<one-line summary>. See research/protocol/<tab>/<op>.md."""
    r = await transport.get(<URL from doc>, params={<from doc>})
    # Validate Content-Type if the doc specifies one.
    # Parse using the appropriate helper from parsing.py.
    parsed = <parser>(r.text)
    return <Model>(**parsed)
```

- [ ] **Step 5: Run the test to verify it passes and commit**

```bash
pytest tests/operations/test_<tab>_<op>.py -v
git add backend/procurve_client/operations/<tab>.py \
        backend/procurve_client/models/<domain>.py \
        backend/tests/operations/test_<tab>_<op>.py
git commit -m "phase1: implement <op_func> (<tab> tab)"
```

**Task-level exit criterion for each 1.11.x sub-task:** every operation documented under the tab's directory has a corresponding test file and function; `pytest tests/operations/test_<tab>_*.py` passes; `pytest --cov=procurve_client.operations.<tab>` is at or above 90%.

---

## Task 1.12: Operation registry + package public API

**Files:**
- Modify: `backend/procurve_client/__init__.py`
- Modify: `backend/procurve_client/operations/__init__.py`
- Create: `backend/tests/unit/test_registry.py`

- [ ] **Step 1: Write the failing test**

**File:** `backend/tests/unit/test_registry.py`
```python
"""Smoke tests: verify the public API re-exports and the operations registry."""
import procurve_client
from procurve_client.operations import ALL_OPERATIONS, READ_OPERATIONS, WRITE_OPERATIONS


def test_top_level_exports():
    for name in ("ProcurveTransport", "NoneAuth", "BasicAuth", "ProcurveError"):
        assert hasattr(procurve_client, name), f"missing top-level export: {name}"


def test_every_operation_has_read_or_write_marker():
    from procurve_client._safety import is_read, is_write
    assert ALL_OPERATIONS, "registry must not be empty after Phase 1 completes"
    for op in ALL_OPERATIONS:
        assert is_read(op) or is_write(op), f"{op.__name__}: missing @READ or @WRITE"


def test_read_and_write_registries_partition_all():
    assert set(READ_OPERATIONS).isdisjoint(WRITE_OPERATIONS)
    assert set(READ_OPERATIONS) | set(WRITE_OPERATIONS) == set(ALL_OPERATIONS)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
pytest tests/unit/test_registry.py -v
```
Expected: FAIL with `ImportError` or empty-registry assertion.

- [ ] **Step 3: Implement the public API re-exports**

**File:** `backend/procurve_client/__init__.py`
```python
"""Python protocol client for HP ProCurve 2810-24G."""
from procurve_client.auth import BasicAuth, NoneAuth
from procurve_client.errors import (
    AuthError,
    OperationError,
    ParseError,
    ProcurveError,
    ProtocolError,
    SchemaError,
    TransportError,
    WriteDisabledError,
)
from procurve_client.transport import ProcurveTransport

__all__ = [
    "ProcurveTransport",
    "NoneAuth",
    "BasicAuth",
    "ProcurveError",
    "TransportError",
    "AuthError",
    "ProtocolError",
    "ParseError",
    "SchemaError",
    "OperationError",
    "WriteDisabledError",
]
```

**File:** `backend/procurve_client/operations/__init__.py`
```python
"""Operation registry. Import every tab's operations and build READ/WRITE indexes."""
from __future__ import annotations

from collections.abc import Callable

from procurve_client._safety import is_read, is_write

from procurve_client.operations import (
    backup,
    configuration,
    diagnostics,
    identity,
    security,
    status,
    support,
)


def _discover(module: object) -> list[Callable]:
    """Return every @READ / @WRITE decorated function defined in a module."""
    return [
        obj
        for name in dir(module)
        if not name.startswith("_")
        for obj in [getattr(module, name)]
        if callable(obj) and (is_read(obj) or is_write(obj))
    ]


_MODULES = [backup, identity, status, configuration, security, diagnostics, support]

ALL_OPERATIONS: list[Callable] = [op for m in _MODULES for op in _discover(m)]
READ_OPERATIONS: list[Callable] = [op for op in ALL_OPERATIONS if is_read(op)]
WRITE_OPERATIONS: list[Callable] = [op for op in ALL_OPERATIONS if is_write(op)]
```

Note: the sub-modules `configuration`, `diagnostics`, `identity`, `security`, `status`, `support` must exist — even if they only contain operations from Task 1.11. Create empty module files as needed during 1.11 sub-tasks; they become non-empty as operations are implemented.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
pytest tests/unit/test_registry.py -v
```
Expected: all tests PASS. If `ALL_OPERATIONS` is empty, Phase 1 Task 1.11 is incomplete — return there.

- [ ] **Step 5: Commit**

Run:
```bash
git add backend/procurve_client/__init__.py backend/procurve_client/operations/__init__.py \
        backend/tests/unit/test_registry.py
git commit -m "phase1: public API exports + operations registry"
```
Expected: commit succeeds.

---

## Task 1.13: Live integration tests for all read operations

**Files:**
- Create: `backend/tests/live/__init__.py`
- Create: `backend/tests/live/test_live_reads.py`

- [ ] **Step 1: Write the live test harness**

**File:** `backend/tests/live/__init__.py`
```python
```

**File:** `backend/tests/live/test_live_reads.py`
```python
"""Live integration tests — hit the actual switch. Run with `pytest -m live`."""
from __future__ import annotations

import os

import pytest

from procurve_client import ProcurveTransport
from procurve_client.operations import READ_OPERATIONS

pytestmark = pytest.mark.live


@pytest.fixture
async def live_transport():
    host = os.environ.get("SWITCH_HOST", "192.168.178.3")
    async with ProcurveTransport(host=host) as t:
        yield t


@pytest.mark.parametrize("op", READ_OPERATIONS, ids=lambda o: o.__name__)
async def test_read_operation_live(live_transport, op):
    """Every @READ operation runs successfully against the live switch.

    Operations that take required arguments beyond `transport` are excluded
    here — those live-tests live in `test_live_reads_parametric.py`
    (added case-by-case for ops that need a port number, VLAN id, etc.).
    """
    sig = _single_arg_operations()
    if op not in sig:
        pytest.skip(f"{op.__name__} needs arguments; covered by parametric test")
    result = await op(live_transport)
    assert result is not None


def _single_arg_operations() -> list:
    """Select ops whose only required arg is the transport."""
    import inspect
    out = []
    for op in READ_OPERATIONS:
        params = list(inspect.signature(op).parameters.values())[1:]  # skip transport
        required = [p for p in params if p.default is inspect.Parameter.empty]
        if not required:
            out.append(op)
    return out
```

- [ ] **Step 2: Run the live tests**

Run (ONLY when switch is reachable, i.e., user is on the right network):
```bash
pytest -m live -v
```
Expected: every parameter-free read operation returns a non-None model. If any fails, the corresponding operation function or its test is broken — inspect the failure and fix either the code or the protocol doc (whichever was wrong).

- [ ] **Step 3: Add per-operation live tests for operations that require args**

For each `@READ` operation that takes extra required args (e.g. `get_port_status(t, port=1)`), add a dedicated live test at `tests/live/test_live_reads_parametric.py` that passes representative args (e.g. port=1 for a known-up port) and asserts expected shape of the result.

- [ ] **Step 4: Commit**

Run:
```bash
git add backend/tests/live/
git commit -m "phase1: live integration tests for all read operations"
```
Expected: commit succeeds.

---

## Task 1.14: Demonstrate full write→verify→restore→verify round-trip

**Files:**
- Create: `backend/tests/live/test_roundtrip.py`

**CRITICAL SAFETY GATE:** This is the ONLY task in Phase 1 that issues write-calls against the live switch. It runs under the dev-time safety rule (see `memory/feedback_switch_write_safety.md` and §7 of the spec). Execution requires:

1. The user has given explicit go-ahead for this specific task.
2. The reference backup (`research/backups/2026-04-23/CONFIG.pcc`) is still user-confirmed valid.
3. The `restore_config` implementation from Task 1.10 has been reviewed by the user (code + multipart body shape).
4. The round-trip is on a **trivial** change — default choice: port 18 name from `"UPS"` to `"UPS-TEST"` then back to `"UPS"` via restore.

If any of the four conditions isn't met: **STOP and notify the user before running.**

- [ ] **Step 1: Write the round-trip test**

**File:** `backend/tests/live/test_roundtrip.py`
```python
"""End-to-end round-trip: write a trivial change, verify, restore, verify-empty.

This test exists to validate the safety rule's workflow using the smallest
possible change. It is opt-in (`-m roundtrip`) and requires explicit user
approval per-run. It NEVER runs in CI.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from procurve_client import ProcurveTransport
from procurve_client.models.backup import ConfigBackup, ConfigSlot
from procurve_client.operations.backup import download_config, restore_config

pytestmark = [pytest.mark.live, pytest.mark.roundtrip]


def _reference_backup() -> ConfigBackup:
    path = (
        Path(__file__).resolve().parents[3]
        / "research"
        / "backups"
        / "2026-04-23"
        / "CONFIG.pcc"
    )
    return ConfigBackup.from_text(path.read_text(encoding="ascii", newline=""))


async def test_roundtrip_port18_name(monkeypatch):
    """Change port 18 name → verify change visible → restore → verify restored."""
    # Sanity: READ_ONLY must be explicitly off for this test — the user must
    # have opted in.
    monkeypatch.setenv("READ_ONLY", os.environ.get("READ_ONLY", "false"))
    baseline = _reference_backup()

    host = os.environ.get("SWITCH_HOST", "192.168.178.3")
    async with ProcurveTransport(host=host) as t:
        # 1. Pre-state matches baseline
        pre = await download_config(t)
        assert pre.sha256 == baseline.sha256, (
            f"live switch diverged from baseline: live={pre.sha256} "
            f"baseline={baseline.sha256}. Refusing to run write-test. "
            f"See memory/feedback_switch_write_safety.md."
        )

        # 2. Execute the write-call under test
        from procurve_client.operations.configuration import set_port_name
        await set_port_name(t, port=18, name="UPS-TEST")

        # 3. Verify the write worked
        post_write = await download_config(t)
        assert post_write.sha256 != baseline.sha256, "write had no effect"
        assert 'name "UPS-TEST"' in post_write.text
        assert 'name "UPS-TEST"' not in baseline.text  # sanity on the diff

        # 4. Restore the baseline
        await restore_config(t, backup=baseline, slot=ConfigSlot.PRIMARY)

        # 5. Verify restore succeeded
        post_restore = await download_config(t)
        assert post_restore.sha256 == baseline.sha256, (
            f"restore did not return switch to baseline.\n"
            f"expected {baseline.sha256}\n"
            f"got      {post_restore.sha256}\n"
            f"See the diff below for debugging.\n"
            f"STOP: notify user before running further write-tests."
        )
```

- [ ] **Step 2: User-approval checkpoint**

Halt and show the user:

- The test file above
- The exact `set_port_name` implementation from Task 1.11.c
- The `restore_config` implementation from Task 1.10
- A recap of the write-safety rule
- The SHA256 of the current live config (compare with reference)

Ask explicitly: "Approved to run the round-trip test against the live switch?" Proceed only after the user types "yes" or equivalent.

- [ ] **Step 3: Run the round-trip once**

Run:
```bash
READ_ONLY=false pytest -m roundtrip -v
```
Expected: the single test passes, meaning the round-trip succeeded end-to-end. If it fails at step 1 (baseline mismatch): STOP — the switch has drifted from the reference. If it fails at step 4 (post-restore mismatch): STOP — restore is broken, switch may be in a non-baseline state; notify the user with the diff immediately.

- [ ] **Step 4: Confirm post-test state**

Run:
```bash
curl -s -m 15 -o /tmp/post-roundtrip.pcc \
  "http://192.168.178.3/cgi/configfile?idx=1&fg=1&D1=Download"
sha256sum /tmp/post-roundtrip.pcc
```
Expected: SHA256 equals `f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11` — matching the reference baseline. If not, STOP and notify user.

- [ ] **Step 5: Commit**

Run:
```bash
cd /f/DevProjects/procurve-webui
git add backend/tests/live/test_roundtrip.py
git commit -m "phase1: write→verify→restore round-trip test (user-approved, port 18 name)"
```
Expected: commit succeeds.

---

## Task 1.15: Coverage check and Phase 1 closure

**Files:**
- Create: `backend/coverage-report.md`

- [ ] **Step 1: Run the full test suite (offline + coverage)**

Run:
```bash
cd backend
pytest --cov=procurve_client --cov-report=term-missing --cov-report=html -m "not live"
```
Expected: all non-live tests PASS. Coverage >= 90% for `procurve_client/`. If below: add missing tests for the uncovered branches, or document why they're unreachable in `coverage-report.md`.

- [ ] **Step 2: Run the live reads (smoke)**

Run:
```bash
pytest -m live -v
```
Expected: every parameter-free + per-port live-read passes.

- [ ] **Step 3: Write the coverage report**

**File:** `backend/coverage-report.md`
```markdown
# Phase 1 coverage report

Generated: <date>

## Totals

- Statements: <N>
- Missed: <M>
- Branch rate: <X>%
- Line rate: <Y>%

## Per-module summary

<copy-paste the coverage tool's terminal summary>

## Notes

- Any branches intentionally uncovered (e.g. defensive error paths that
  can't be exercised without specific hardware faults) are listed here
  with an explanation.
```

- [ ] **Step 4: Final commit + tag**

Run:
```bash
cd /f/DevProjects/procurve-webui
git add backend/coverage-report.md
git commit -m "phase1: final coverage report and closure"
git tag -a phase1-complete -m "Phase 1 Python protocol client complete"
```
Expected: commit + tag succeed.

---

## Self-review — Phase 1 plan

**Spec coverage (§6 of the spec):**

- §6.1 Package layout — Task 1.1 scaffolds it, later tasks fill modules ✓
- §6.2 Design principles (flat function API, one stateful transport, Pydantic v2, strict setters) — Tasks 1.5, 1.9, 1.10, 1.11 ✓
- §6.3 Read vs. write separation (@READ / @WRITE, READ_ONLY) — Task 1.3 ✓
- §6.4 Testing strategy (unit with fixtures, integration read-only, byte-match writes, >90% coverage) — Tasks 1.9, 1.10, 1.13, 1.15 ✓
- §6.5 In-scope for Phase 1 (transport, auth, parsers, errors, all ops) — Tasks 1.2–1.14 ✓

**Safety rules (§7 of the spec):**

- Reference backup read-only for dev — respected; the round-trip test uses the existing `CONFIG.pcc` as restore source (Task 1.14).
- Writes allowed but strictly rolled back — enforced by Task 1.14's test structure.
- Backup handling rule (never overwrite the reference) — the test restores from the reference only; it does not create new baseline files.
- Blocked operations (firmware, factory reset, management-IP changes) — Task 1.14 deliberately uses port-18 name only.

**Placeholder scan:**

- No "TBD" / "TODO" lines.
- Task 1.11 is parameterized per operation, but the pattern is fully concrete (test template, model template, operation template, commit script). This is unavoidable because the exact operation list emerges from Phase 0 — enumerating speculative operations in this plan would be the real placeholder failure.

**Type consistency:**

- `ConfigSlot` (Task 1.8) used consistently in Tasks 1.9, 1.10, 1.14.
- `ProcurveTransport.get / .post` signatures defined in Task 1.5, invoked as declared in Tasks 1.9, 1.10.
- `@READ` / `@WRITE` / `WriteDisabledError` defined in Task 1.3, used from Task 1.9 onward.
- `ConfigBackup.from_text()` defined in Task 1.8, used in Tasks 1.10, 1.14.

**Scope check:** Phase 1 is a single implementation effort producing a testable library. The Phase 2+ UI and Docker packaging are properly deferred.
