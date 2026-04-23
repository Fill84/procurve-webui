# set_fault_detection

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/web_agent.html:70`
(`<form name=features action="../cgi/web_agent">`), with the
`<select name=ffs>` at lines 87-92 offering the four sensitivity
options. The frameset entry is
`research/mirror/2026-04-23/configuration/web_agentf.html:3`.
Sub-tab key in menu: `faultdetect` (menu.html:42).

## HTTP contract

- **Method:** GET (native HTML `<form>` with no `method=` attribute
  defaults to GET, matching the tab-wide convention).
- **URL template:** `/cgi/web_agent?ffs={sensitivity}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | ffs | integer, one of `0`, `32`, `128`, `224` | yes | Sensitivity level. See the value table below. Values come from web_agent.html:88-91. |

  Sensitivity values:

  | ffs | Label |
  |---|---|
  | `0` | Never (fault detection disabled) |
  | `32` | High Sensitivity (Recommended) — factory default |
  | `128` | Medium Sensitivity |
  | `224` | Low Sensitivity |

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** presumed short `OK~...` line or switch-
  generated HTML redirect. **Not live-tested** — write operations
  are not exercised in Phase 0.
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| sensitivity | `ffs` | integer literal | `Literal[0, 32, 128, 224]` | exact value list | Map Python-side to an enum. |

## Reading the current value

The Fault Detection tab has **no dedicated CGI for reading** the
current sensitivity. The live value is injected by the switch
directly into `web_agent.html` as a JavaScript variable:

```
ffs=32;
dps=1;
    var ffSetting = ffs ;   // GETFFCFG sets ffs and dps
```

(web_agent.html:31-33 — the comment `GETFFCFG` refers to the
server-side template macro that substitutes these values at page
generation time, not to a separate CGI call.)

A Python client that wants to read the current sensitivity must
GET `http://<switch>/configuration/web_agent.html` and regex-scrape
the `ffs=<digits>;` line near the top of the body. This pattern is
shared by several other Configuration sub-tabs (system, support,
ip2, features2) and is tracked as a follow-up: consider a generic
`read_injected_js_var(page, var_name)` helper in Phase 1.

## Example request

```
GET /cgi/web_agent?ffs=32 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class FaultSensitivity(IntEnum):
    NEVER = 0
    HIGH = 32
    MEDIUM = 128
    LOW = 224


class SetFaultDetectionRequest(BaseModel):
    sensitivity: FaultSensitivity  # serialises to ffs=<int>


class SetFaultDetectionResponse(BaseModel):
    ok: bool  # inferred from HTTP status
```

## Notes & caveats

- **`dps` is a second injected variable** visible in the scraped
  HTML (web_agent.html:32). It is never read by the live form (no
  `dps` <input> or <select> exists), so it appears to be a
  read-only telemetry field with no mutation path through the web
  UI. Ignored for this operation.
- **Only `ffs` is submitted.** The `<select>` sits inside a form
  that has no other submit-bearing inputs; the submit button posts
  exactly one query param.
- **`fflog?action=status` is unrelated** despite the name. That
  endpoint returns the alert-banner text rendered in
  `ncidbar.html`; it is documented under `status/get_device_status.md`.
- **Related:** `fflog?action=list` (status/get_alert_log.md) — the
  list of faults that fault detection has recorded.
