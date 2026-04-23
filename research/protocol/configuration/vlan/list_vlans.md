# listVLANS

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANAddRemovePanel.java:359` (URL built as
`getBaseCgiUrl() + "listVLANS"`); parsed at
`VLANAddRemovePanel.java:240-280` (`callURLlist`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/listVLANS`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, a single tilde-delimited record
  containing `(vlan_id, vlan_name)` pairs packed inline. **No
  `OK~` sentinel.**

  Layout (repeats per VLAN):
  ```
  <vlan_id>~<vlan_name>~<vlan_id>~<vlan_name>~...
  ```
  A trailing `~` is present after the final name.

- **Success indicator:** HTTP 200 with at least one `(id, name)`
  pair. The applet tolerates a leading blank line and re-reads on
  length-zero (`VLANAddRemovePanel.java:253-255`).
- **Error indicators:** Non-200; empty body.

## Field reference

Per pair:

| field | wire position (within pair) | wire type | python type | notes |
|---|---|---|---|---|
| vlan_id | 0 | decimal integer | `int` | |
| vlan_name | 1 | string | `str` | Primary VLAN includes ` (Primary)` suffix. |

## Example request

```
GET /cgi/listVLANS HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__listVLANS.response.txt` (live-captured
2026-04-23, 27 bytes).

Raw body:
```
1~DEFAULT_VLAN (Primary)~
```

A multi-VLAN switch would emit `1~DEFAULT_VLAN (Primary)~10~Guests~20~Servers~` etc.

## Pydantic sketch

```python
from pydantic import BaseModel


class VlanRef(BaseModel):
    vlan_id: int
    vlan_name: str


class ListVlansResponse(BaseModel):
    vlans: list[VlanRef]
```

## Notes & caveats

- **Separate endpoint from `getVLANAll`.** `listVLANS` returns only
  `(id, name)` pairs — no port-list or type metadata — because it
  populates the Add/Remove panel's left-hand MultiList widget which
  only shows VLAN ids and names. `getVLANAll` returns full records
  and populates the summary table on the first panel.
- **Parser loops `hasMoreTokens`.** The Java consumer (`callURLlist`)
  iterates `StringTokenizer` pairs regardless of line boundaries,
  so the Python parser can treat the whole body as a single
  tilde-split stream and chunk it two-at-a-time.
- **Invoked on panel entry.** `getDataForList()` is called via
  `setScreen(1, ...)` at `VLANmain.java:102`, i.e. every time the
  user clicks "ADD/REMOVE VLANs". It is also called after each
  successful add/delete/rename as part of `callURLwithUpdate`
  (which reuses the same response shape — see
  `VLANAddRemovePanel.java:197-221`).
</content>
</invoke>