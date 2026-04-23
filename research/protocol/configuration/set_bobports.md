# set_bobports

**Tab:** configuration
**Kind:** write
**Source in applet:** `SwitchBob.java:280-298` (`setEnableForSelectedPorts`
assembles the `?ifAdminStatus=...&indeces=...` query string);
`SwitchBob.java:301-312` (`callback()` opens
`new URL(getCodeBase(), m_setURLname + m_query)`).
The `XFishBob` subclass used by the 2810-24G closeup has the same
contract — `XFishBob.java:289-296` (setEnableForSelectedPorts) and
`XFishBob.java:322-332` (callback, using `getDocumentBase()` instead
of `getCodeBase()`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/device_view.html:54`
(`<param name=setURL value="../cgi/set_bobports">`). The Enable /
Disable buttons (device_view.html:193-202) call
`document.bob.setEnableForSelectedPorts(true/false)` on the applet.

## HTTP contract

- **Method:** GET (mutation encoded in query string — per
  `_conventions.md`)
- **URL template:** `/cgi/set_bobports?ifAdminStatus={1|2}&indeces={csv}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | ifAdminStatus | `1` or `2` | yes | `1` = enable, `2` = disable. Set at `SwitchBob.java:282`: `"?ifAdminStatus=" + (bl ? "1" : "2")`. |
  | indeces | comma-separated port numbers | yes | Ports to act on. Note the misspelling `indeces` — preserve verbatim on the wire. Assembled at `SwitchBob.java:291-293` by iterating the selected `Drawable`s and appending `this.extractIF(drawable.name())`. |

  Comma between ports is URL-encoded at `ListPane.java:572`
  (`URLEncoder.encode(",")` = `%2C`); `SwitchBob.java:291` uses a
  literal `","`, so a single-port submit sends no comma at all and
  multi-port submits send literal commas. The switch accepts both
  `,` and `%2C` (observed for the VLAN family).

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response body:** the applet immediately loops back to
  `updateStatus()` (SwitchBob.java:305) to re-poll `get_bobports`;
  the response body of the `set_bobports` call itself is not
  consumed by the applet. It is presumed to be a short
  `OK~` / `error~<message>` line, matching the rest of the
  protocol, but **this is unverified — live test required**.
- **Success indicator:** HTTP 200; further confirmation comes from
  the follow-up `get_bobports` poll showing the new admin state.
- **Error indicators:** Non-200 HTTP. **Exact error-body format
  unverified — needs live capture.**

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| enable | `ifAdminStatus` | `1` or `2` | `bool` mapped to `1` (True) / `2` (False) | exact values | No other values accepted by the Java caller. |
| ports | `indeces` | comma-separated int list | `list[int]` | `len >= 1` | Port numbers. Preserve the misspelling on the wire. |

## Example request

Enable ports 1, 2, 3:
```
GET /cgi/set_bobports?ifAdminStatus=1&indeces=1,2,3 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Disable port 5 only:
```
GET /cgi/set_bobports?ifAdminStatus=2&indeces=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested
per Phase-0 safety rules.

## Pydantic sketch

```python
from pydantic import BaseModel, Field, field_validator


class SetBobPortsRequest(BaseModel):
    enable: bool  # serialise to ifAdminStatus: True -> "1", False -> "2"
    ports: list[int] = Field(min_length=1)  # serialise as comma-joined indeces

    @field_validator("ports")
    @classmethod
    def must_be_positive(cls, v: list[int]) -> list[int]:
        if any(p < 1 for p in v):
            raise ValueError("ports must be >= 1")
        return v


class SetBobPortsResponse(BaseModel):
    # placeholder — exact wire format unverified; expected to match the
    # OK~... / error~... convention used elsewhere
    ok: bool
    message: str | None = None
```

## Notes & caveats

- **Operation is fire-and-poll.** The applet does not consume the
  response body; it triggers a re-poll of `get_bobports` to reflect
  the new state (SwitchBob.java:305). A Python client should either
  follow the same two-call pattern or trust the HTTP status + a
  subsequent `get_bobports` read.
- **Wire misspelling `indeces` is mandatory.** `_conventions.md`
  requires byte-exact preservation.
- **Command separator.** Single-port calls emit no comma; this
  matches `SwitchBob.java:290` (`if (!bl2) append ","`). Python's
  `",".join(str(p) for p in ports)` reproduces this.
- **Does not carry port-config fields.** `ifAdminStatus` is the
  only mutable field via this CGI. Speed/duplex/flow-control live
  behind `/cgi/mod_ports` (see `set_port_config.md`).
- **Related:** `get_bobports` — companion read. `set_port_config`
  (`/cgi/mod_ports`) — the deeper per-port edit form.
