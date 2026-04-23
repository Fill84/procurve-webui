# get_portscfg

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java:29, 47-80` (init reads
`dataURL`, `formURL`, `titles`, `columns`, `params` applet params;
loads data through `ListPane`). Used exactly like `get_ports`
(status) and `portc` (port counters).
**Source in HTML:** `research/mirror/2026-04-23/configuration/ports1.html:31-39`
(`<applet code=GenericList.class>` with
`<param name=dataURL value="../cgi/get_portscfg">`,
`<param name=formURL value="../cgi/port_form">`,
`<param name=target value="nc_view">`,
`<param name=titles value="Port~Port Name~Port%Type~Enabled~?Status~Config%Mode~?Trunk~Flow%Control">`,
`<param name=columns value="60~150:x~240~330~339:h~420~429:h~510">`,
`<param name=params value=".~.~.~.~.~.~.~.~.">`).
Frameset entry: `portsf.html:3`.
Sub-tab key in menu: `ports` (menu.html:42).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_portscfg`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, LF-separated, tilde-delimited.
  No sentinel — bare-row stream, one row per port.

  Observed row (9 fields):
  ```
  <port>~<port_name>~<port_type_label>~<port_type>~<enabled>~<config_status>~<config_mode>~<trunk>~<flow_control>~<extra>
  ```
  Mapping to the 8 declared title columns
  (`Port~Port Name~Port%Type~Enabled~?Status~Config%Mode~?Trunk~Flow%Control`):
  - position 0 `<port>` → "Port".
  - position 1 `<port_name>` → "Port Name" (user-set label).
  - position 2 `<port_type_label>` → hidden/decorative tag
    (observed `" "` on every row on the 2810). Mirrors
    `get_ports` position 2.
  - position 3 `<port_type>` → "Port Type" (e.g. `100/1000T`).
  - position 4 `<enabled>` → "Enabled" (`Yes` / `No`).
  - position 5 `<config_status>` → "?Status" (hidden by default;
    observed `.` on all rows — i.e. "nothing to report").
  - position 6 `<config_mode>` → "Config Mode" (e.g.
    `Auto-1000`, `Auto`, `Auto-10-100`, etc — the configured
    mode, not the negotiated one).
  - position 7 `<trunk>` → "?Trunk" (hidden by default, space when
    unassigned).
  - position 8 `<flow_control>` → "Flow Control" (`Enable` /
    `Disable`).
  - position 9 `<extra>` → trailing `0` on every observed row —
    not mapped to any column. Same pattern as `get_ports`
    position 9.

- **Success indicator:** HTTP 200 with at least one tilde-
  delimited row whose first token parses as an integer.
- **Error indicators:** Non-200 HTTP; HTML body instead of text.

## Field reference

| field | wire position | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| port | 0 | decimal integer | `int` | `>= 1` | |
| port_name | 1 | string | `str` | may be empty | User-assigned name; defaults to the port number. |
| port_type_label | 2 | string | `str` | | Typically `" "`. |
| port_type | 3 | string | `str` | | e.g. `100/1000T`. |
| enabled | 4 | `Yes`/`No` | `bool` | | Admin state. |
| config_status | 5 | string | `str` | | `.` = no additional status. |
| config_mode | 6 | string | `str` | | e.g. `Auto-1000`, `100FDx`. Mirrors the port_form select. |
| trunk | 7 | string | `str` | | Trunk group name; space when unassigned. |
| flow_control | 8 | `Enable`/`Disable` | `bool` | | Maps to `hpSwitchPortFlowControl` value on write. |
| _extra | 9 | decimal integer | `int` | observed `0` | Purpose unknown; ignore. |

## Example request

```
GET /cgi/get_portscfg HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_portscfg.response.txt` (live-captured
2026-04-23, 1109 bytes).

Excerpt:
```
1~1-Dyn1~ ~100/1000T~Yes~.~Auto-1000~ ~Enable~0
2~2-Dyn1~ ~100/1000T~Yes~.~Auto-1000~ ~Enable~0
3~3-Dyn3~ ~100/1000T~Yes~.~Auto-1000~ ~Enable~0
...
18~18~UPS~100/1000T~Yes~.~Auto-100~ ~Enable~0
...
```

## Pydantic sketch

```python
from pydantic import BaseModel


class PortConfig(BaseModel):
    port: int
    port_name: str
    port_type_label: str = ""
    port_type: str
    enabled: bool
    config_status: str = "."
    config_mode: str
    trunk: str = " "
    flow_control: bool
    _extra: int = 0


class PortConfigList(BaseModel):
    ports: list[PortConfig]
```

## Notes & caveats

- **Near-duplicate of `get_ports`.** The Status-tab `get_ports`
  and the Configuration-tab `get_portscfg` emit nearly identical
  rows. Difference: position 5 is "Link Status" (`Up`/`Down`)
  on `get_ports` but "Config Status" (`.`) on `get_portscfg`;
  position 6 is "Current Mode" vs "Config Mode". Python models
  should be distinct despite the shape overlap.
- **Paired with `port_form` for edits.** The GenericList click
  handler submits a single-row edit via
  `submitMultipleItems(formURL, ...)` (ListPane.java:560-618).
  `formURL=../cgi/port_form` (ports1.html:34) returns an HTML
  form that in turn submits to `/cgi/mod_ports`. See
  `get_port_form.md` and `set_port_config.md`.
- **`params` is all-dot.** The applet param `params=.~.~.~.~.~.~.~.~.`
  (9 dots) means every column is rendered plain-text and none
  appears in the edit form body (ListPane.java:581: only non-`.`
  `params[n]` entries are appended as `&<param>=<value>`). So the
  dataURL has 9 content fields but `port_form` takes only
  `indeces=<port>`.
