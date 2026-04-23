# get_port_status

**Tab:** status
**Kind:** read
**Source in applet:** `GenericList.java:29, 177-179` (reads the
`dataURL` applet param and passes it to `ListPane.loadData`;
`ListPane.java:471-474` opens the GET and reads the tilde-delimited
rows).
**Source in HTML:** `research/mirror/2026-04-23/status/portStatus1.html:33-40`
(the `GenericList` applet host; dataURL = `../cgi/get_ports`). Manual
refresh button is in
`research/mirror/2026-04-23/status/portStatus2.html:5-8`
(`submitMultipleItems('../cgi/get_ports', '', '_loopback', false, false)`).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/get_ports`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, LF-separated lines, tilde-delimited
  fields. One row per physical port, in port-number order (1..N).
  No leading `OK~` sentinel — bare-row stream as for all
  `GenericList` dataURLs.

  Each row has 10 fields (portStatus1.html:37 declares 8 rendered
  columns; the wire emits two extra trailing fields — see below).

  Layout (per column headers `Port~Port Name~Port Type~Enabled~
  Link%Status~Current%Mode~?Trnk~Flow Ctrl` — portStatus1.html:37):
  ```
  <port>~<port_name>~<port_type_label>~<port_type>~<enabled>~<link_status>~<current_mode>~<trunk>~<flow_ctrl>~<unknown>
  ```
  positions vs titles:
  - position 0 `<port>` → "Port"
  - position 1 `<port_name>` → "Port Name"
  - position 2 `<port_type_label>` → (hidden / decorative; typically
    a space or free-form label like `UPS`)
  - position 3 `<port_type>` → "Port Type" (e.g. `100/1000T`)
  - position 4 `<enabled>` → "Enabled" (`Yes` / `No`)
  - position 5 `<link_status>` → "Link Status" (`Up` / `Down`)
  - position 6 `<current_mode>` → "Current Mode" (e.g. `1000FDx`,
    `100FDx`)
  - position 7 `<trunk>` → "Trnk" (hidden by default, `:h` in
    `columns` param; space when unassigned)
  - position 8 `<flow_ctrl>` → "Flow Ctrl" (e.g. `on(Tx+Rx)`, `off`)
  - position 9 `<unknown>` — trailing numeric, observed to be `0`
    on every port in the capture; not rendered in any column.

- **Success indicator:** HTTP 200 with at least one tilde-delimited
  row whose first token parses as an integer port number.
- **Error indicators:** Non-200 HTTP; HTML body instead of text.

## Field reference

| field | wire position | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| port | 0 | decimal integer | `int` | `>= 1` | 1-based port number. |
| port_name | 1 | string | `str` | may be empty | e.g. `1-Dyn1`; defaults to the port number when unset. |
| port_type_label | 2 | string | `str` | may be `" "` | A short tag rendered in a hidden column (e.g. `UPS` on the observed fixture's port 18). Typically a single space. |
| port_type | 3 | string | `str` | | e.g. `100/1000T`. |
| enabled | 4 | literal `Yes`/`No` | `bool` | | admin state. |
| link_status | 5 | literal `Up`/`Down` | `Literal['Up', 'Down']` | | `Down` when no carrier. |
| current_mode | 6 | string | `str` | | Link speed/duplex, e.g. `1000FDx`, `100FDx`. |
| trunk | 7 | string | `str` | `" "` when unassigned | Trunk group name; hidden column by default. |
| flow_ctrl | 8 | string | `str` | | e.g. `on(Tx+Rx)`, `off`. |
| _extra | 9 | decimal integer | `int` | `== 0` in every observed row | Purpose unknown — **needs further investigation or live capture under alternate conditions**. Safely ignored by the GUI. |

## Example request

```
GET /cgi/get_ports HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_port_status.response.txt` (live-captured
2026-04-23, 1133 bytes, SHA256
`7b11330ab826707992233721b62767a75c1f0a02a358a70aa8e0dcd99418fbe0`).

Excerpt:
```
1~1-Dyn1~ ~100/1000T~Yes~Up~1000FDx~ ~on(Tx+Rx)~0
2~2-Dyn1~ ~100/1000T~Yes~Up~1000FDx~ ~on(Tx+Rx)~0
...
18~18~UPS~100/1000T~Yes~Up~100FDx~ ~on(Tx+Rx)~0
...
23~23~ ~100/1000T~No~Down~1000FDx~ ~off~0
24~24~ ~100/1000T~Yes~Up~1000FDx~ ~on(Tx+Rx)~0
```

## Pydantic sketch

```python
from typing import Literal
from pydantic import BaseModel


class PortStatus(BaseModel):
    port: int
    port_name: str
    port_type_label: str = ""
    port_type: str
    enabled: bool
    link_status: Literal["Up", "Down"]
    current_mode: str
    trunk: str = ""
    flow_ctrl: str
    _extra: int = 0  # purpose unknown; observed 0 on all ports


class PortStatusList(BaseModel):
    ports: list[PortStatus]
```

## Notes & caveats

- **Title column count (8) does not match wire column count (10).**
  The extra field at position 2 is a label/tag cell (observed
  `UPS` on port 18, a space on all others); the trailing field at
  position 9 is always `0` in the observed capture. Both are
  silently hidden in the GUI by the `columns`/`params` layout.
  Our parser accepts 10 fields and maps them to the 8 GUI columns
  plus the two auxiliaries.
- **No sentinel.** Bare tilde-delimited rows; match the VLAN
  `listVLANS` pattern documented in `research/analysis/callback-layer.md`.
- **Related to `get_portscfg` (Configuration tab).** The Port
  Configuration tab uses `/cgi/get_portscfg` (see
  `research/analysis/applet-params.md` /configuration/ports1.html);
  that endpoint has the same shape plus a Config Mode column, and
  is writable via `/cgi/port_form`. Not part of the Status tab.
- **Refresh interval.** No `delay` param on portStatus1.html, so
  the table is static until the user clicks `Refresh` in
  portStatus2.html. A Python client polling at e.g. 5 s will be
  closer to live.
- **Whitespace cells.** Multiple cells contain a literal single
  space (`" "`) rather than an empty string. Preserve on parse —
  strip for display.
