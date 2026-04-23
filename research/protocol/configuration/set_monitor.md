# set_monitor

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only. The applet on
`monitor2b.html` (not mirrored; served dynamically when monitoring
is enabled) is a `GenericList` that provides port selection; the
actual submit happens through the HTML `<form>` on monitor1.html.
**Source in HTML:** `research/mirror/2026-04-23/configuration/monitor1.html:92-94`
(`<form name=mpset0 action="../cgi/set_monitor">` with
`<input type=hidden name="portCopyStatus" value=2>`) — disables
monitoring.
`research/mirror/2026-04-23/configuration/monitor1.html:96-100`
(`<form name=mpset1 action="../cgi/set_monitor">` with
`portCopyStatus=4`, `portCopyDest`, `portCopySourceMask`) —
enables monitoring to a chosen destination port.
The `apply()` JS function (monitor1.html:61-86) picks between the
two forms based on the `mpmode` radio state, fills the form fields
from the selected ports, and calls `form.submit()`.
Sub-tab key: `monitor` (menu.html:45).

## HTTP contract

- **Method:** GET
- **URL template** (disable):
  `/cgi/set_monitor?portCopyStatus=2`

  **URL template** (enable):
  `/cgi/set_monitor?portCopyStatus=4&portCopyDest={dest_port}&portCopySourceMask={bitmask}`

- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | portCopyStatus | `2` or `4` | yes | `2` = monitoring off, `4` = monitoring on. The literal values are set as hidden inputs (monitor1.html:93,97). |
  | portCopyDest | integer | when `portCopyStatus=4` | The monitoring (mirror destination) port. Populated from the `monitoringPort` select (monitor1.html:129-145) by `apply()` (line 73). |
  | portCopySourceMask | integer | when `portCopyStatus=4` | Bitmask of source ports (the ports whose traffic is duplicated to the destination). Computed by `parent.mpmf.document.list.getPortMask()` (monitor1.html:75) — this is a `GenericList` helper in the applet-hosted sibling frame. Interpret as a big-integer bitmask: bit `n` set = port `n+1` selected. |

- **Request body:** none (GET).
- **Response body:** **not live-tested.**
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP; or alert `"Monitor Port can not
  be same as Mirror Port"` (monitor1.html:80-83) — client-side
  validation prevents destination == a selected source.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| status | `portCopyStatus` | `2`/`4` | `bool` | True (enable) → `4`, False (disable) → `2`. |
| dest_port | `portCopyDest` | integer | `int \| None` | Required when enabling. On the 2810 observed defaults: any port not in the source set. |
| source_mask | `portCopySourceMask` | integer bitmask | `int \| None` | Required when enabling. Ports whose traffic to mirror. |

## Reading the current values

No dedicated read CGI. The state is injected into monitor1.html:
```
var probeStatus   = 2 ;
var probeType     = 0 ;
```
(monitor1.html:32-33). `probeStatus == 1` → monitoring on;
`probeStatus == 2` → monitoring off. The current source ports and
destination port are not obviously injected — on this switch the
list of selectable destination ports (monitor1.html:129-145)
excludes some ports (7, 8, 11-14, 17-24 are listed; 1-6, 9-10,
15-16 are missing — these presumably have some constraint such as
being trunk members). Live scrape of monitor1.html is needed for
state discovery.

## Example request

Disable monitoring:
```
GET /cgi/set_monitor?portCopyStatus=2 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Enable monitoring, mirror ports 1+2 (source_mask = 0b11 = 3) to
destination port 24:
```
GET /cgi/set_monitor?portCopyStatus=4&portCopyDest=24&portCopySourceMask=3 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, model_validator


class SetMonitorRequest(BaseModel):
    enabled: bool
    dest_port: int | None = None
    source_mask: int | None = None

    @model_validator(mode="after")
    def enabled_requires_dest_and_mask(self) -> "SetMonitorRequest":
        if self.enabled and (self.dest_port is None or self.source_mask is None):
            raise ValueError("enabling monitoring requires dest_port and source_mask")
        return self


class SetMonitorResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Two forms, one endpoint.** The JS chooses between `mpset0`
  (status=2) and `mpset1` (status=4) at apply time. A Python
  client collapses to one function that emits either shape.
- **Bitmask semantics.** `getPortMask()` in `GenericList` is not
  obvious from the decompiled source; the applet treats the list
  positions as bit positions. **Needs live capture** to confirm
  whether bit 0 corresponds to port 1 or port 0, and whether the
  mask is sent as a decimal integer or hex.
- **No CGI read.** Scraping monitor1.html is the only way to read
  the current state.
