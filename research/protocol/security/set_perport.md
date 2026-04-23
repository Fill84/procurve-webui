# set_perport

**Tab:** security
**Kind:** write
**Source in applet:** none — the write is a plain HTML form submit.
**Source in HTML:** `research/mirror/2026-04-23/security/perport_form1.html` (live-fetched 2026-04-23). Form declaration at L167:

```
<form name="psf" action="../cgi/perport">
<input type=hidden name=GR value="">
<input type=hidden name=tr value="">
<input type=hidden name=pt value="">
<input type=hidden name=indeces value="">
...
```

## HTTP contract

- **Method:** GET (no `method="POST"` attribute on the form — HTML default is GET).
- **URL template:** `/cgi/perport?GR={group}&tr={trunk}&pt={port}&indeces={indeces}&mode={mode}&sa={security_action}&adl={address_limit}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | `GR` | string | yes | Stack group (empty on standalone) |
  | `tr` | int | yes | Trunk flag (0 = non-trunked) — hidden field, copied from the read row |
  | `pt` | int | yes | Port number |
  | `indeces` | comma-separated ints | yes | Selected row index(es); preserve misspelling |
  | `mode` | int | yes | Address Selection code: `1`=Continuous, `2`=Static, `5`=Port Access (see `perport_form1.html:132-147`); the HTML `<select name=mode>` maps positions to firmware codes |
  | `sa` | int | yes | Security action / alert (1=None, 2=Send Alarm, 3=Send Alarm and Disable Port — inferred from form options) |
  | `adl` | int | yes | Authorized device limit (1-8 for Static, or Limited max from the options list) |

  Additional fields appear when Static or Port-Access modes are configured; they live in the secondary frame `perport_form2.html` / `perport_form4.html` and add the specific authorized-MAC value(s). That frame was not mirrored separately for Phase 0; its exact param shape is `unknown — needs live capture under user supervision`.

- **Request headers:** standard.
- **Request body:** none (GET).
- **Response headers (relevant):** `unknown — needs live capture under user supervision`.
- **Response body:** `unknown — needs live capture under user supervision`. Consistent with sibling CGIs, expect either a redirect to `/security/perportsf.html` or a short `OK~`/`error~` line.
- **Success indicator:** HTTP 200, body not prefixed `error~`. `unknown — needs live capture under user supervision`.
- **Error indicators:** body starting with `error~`.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| group | `GR` | querystring | `str` | empty on standalone | preserved verbatim |
| trunk | `tr` | querystring int | `int` | `0` expected (non-trunked); `1` ports cannot have security configured (the HTML alerts and bounces) | copied from the matching `get_perports` row |
| port | `pt` | querystring int | `int` | 1..N | |
| indeces | `indeces` | comma-sep ints | `list[int]` | | preserve misspelling |
| mode | `mode` | querystring int | `PortSecurityMode` | `1`=Continuous, `2`=Static, `5`=Port Access (see JS at `perport_form1.html:132-147`) | full enum requires live confirmation |
| security_action | `sa` | querystring int | `SecurityAction` | `1`=None; higher values = alert + action | enum values to be confirmed live |
| address_limit | `adl` | querystring int | `int` | 1..8 typical | |

## Example request (prepared — NOT live-tested)

Set port 18 to Static mode with address limit 1, no alert action:
```
GET /cgi/perport?GR=&tr=0&pt=18&indeces=18&mode=2&sa=1&adl=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Not captured. This is a genuine-write operation — per `memory/feedback_switch_write_safety.md` we do NOT live-test writes in Phase 0 even when not in the forbidden set.

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class PortSecurityMode(IntEnum):
    CONTINUOUS = 1
    STATIC = 2
    PORT_ACCESS = 5  # value from perport_form1.html:135


class SecurityAction(IntEnum):
    NONE = 1
    SEND_ALARM = 2  # unconfirmed — needs live capture
    SEND_ALARM_DISABLE = 3  # unconfirmed


class SetPerportRequest(BaseModel):
    port: int
    trunk: int = 0
    group: str = ""
    mode: PortSecurityMode
    security_action: SecurityAction = SecurityAction.NONE
    address_limit: int = 1
    indeces: list[int]  # misspelled on wire


class SetPerportResponse(BaseModel):
    applied: bool
    message: str | None = None
```

## Notes & caveats

- **Not "absolutely forbidden", but still not live-tested in Phase 0.** This write touches per-port MAC-security, which could disable a port if set incorrectly for a port that carries management traffic. Under the general write-safety rule we defer invocation to Phase 1 Task 1.14 with user approval.
- **Mode-dependent sub-fields.** Static mode requires an additional authorized MAC address — the HTML steers the bottom frame to `perport_form2.html` or `perport_form4.html` to collect that. Phase 0 documentation captures the top-level form only; Phase 1 will add the sub-frame fields.
- **Trunk guard.** The JS pops `alert("Trunk and meshed ports cannot have security features configured.");` and bounces the frame if `tr == 1`. The client must enforce the same precondition before sending.
- **Misspelling preserved:** `indeces`.
