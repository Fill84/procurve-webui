# device_reset

> ⚠️ **FORBIDDEN** — this operation is documented for protocol-parity only. It
> MUST NOT be invoked (not even with user approval) during Phase 0.
> A device reset interrupts all switched traffic for the duration of the
> boot cycle and can leave the management LAN unreachable for minutes.
> See `memory/feedback_switch_write_safety.md`.

**Tab:** diagnostics
**Kind:** write
**Source in applet:** none — plain HTML form.
**Source in HTML:** `research/mirror/2026-04-23/diagnostics/reset.html` L34:
```
<form name=dr action="../cgi/device_reset">
...
<input type=button value=" Reset Device " i18n
    onClick="if (confirm ('Really reset the device?')) submit();" i18n>
```

## HTTP contract

- **Method:** GET (HTML default).
- **URL template:** `/cgi/device_reset`
- **Query params:** none. The submit button is a plain `<input type=button>` without a `name`, so no field is carried; the `onClick` handler calls `submit()` after a JS `confirm()` prompt.
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):** `unknown — needs live capture under user supervision` (forbidden).
- **Response body:** `unknown — needs live capture under user supervision`. Typically the TCP connection is reset mid-response as the switch reboots — clients should expect `ConnectionResetError` and treat it as a successful invocation.
- **Success indicator:** TCP reset during response, followed by management IP becoming unreachable for ~60-120 seconds. `unknown — needs live capture`.
- **Error indicators:** HTTP 401 (not authenticated), HTTP 403 (not authorized). A HTTP 200 + body containing `error` is also plausible but unconfirmed.

## Field reference

No fields.

## Example request (prepared — NOT live-tested)

```
GET /cgi/device_reset HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured. The FORBIDDEN banner prohibits live invocation.

## Pydantic sketch

```python
from pydantic import BaseModel


class DeviceResetRequest(BaseModel):
    pass  # no inputs


class DeviceResetResponse(BaseModel):
    initiated: bool  # True if we got HTTP 200 or connection-reset before completion
    message: str | None = None
```

## Notes & caveats

- **Absolutely forbidden.** Reboot operations are in the explicit forbidden set from the task brief.
- **Handle connection reset as success.** Python's `httpx`/`requests` will raise on a server-initiated TCP RST mid-response. Phase 1 client must catch that specific exception and treat it as "reset initiated" rather than bubbling the error up.
- **No confirmation token.** Unlike modern APIs that require a confirmation nonce, this CGI reboots on bare GET. Accidentally hitting the URL (e.g., via browser history, URL preview, prefetch, or an over-eager test) will reboot the switch. The Python client must require explicit `ConfirmReset()` boolean and never log the URL to any cacheable location.
- See `memory/feedback_switch_write_safety.md`.
