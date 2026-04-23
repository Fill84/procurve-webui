# getVLANAll

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANTable.java:181` (invoked through
`GenericTable.updateTable("getVLANAll")` from `VLANfirstPanel.java:209`;
parsed tokeniser at `VLANTable.java:189-221`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getVLANAll`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, one VLAN per line, tilde-delimited.
  **No `OK~` sentinel** — each row is a bare data record.

  Field layout for `family=1` (Infinity — our 2810):
  ```
  <vlan_id>~<vlan_name>~<vlan_type>~<tagged_ports>~<gvrp_ports>~<untagged_ports>~<forbid_ports>~<auto_ports>
  ```
  Pipe (`|`) is used as an intra-field port separator inside any of
  the port lists; the applet converts `|` to `,` for display
  (`VLANTable.java:202-214`). `None` means the list is empty.

- **Success indicator:** HTTP 200 with at least one well-formed line
  whose first token parses as an integer VLAN ID.
- **Error indicators:** Non-200 HTTP, or an empty body.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| vlan_id | 0 | decimal integer | `int` | 1 = DEFAULT_VLAN (always present). |
| vlan_name | 1 | string | `str` | Primary VLAN has ` (Primary)` suffix baked into the name. |
| vlan_type | 2 | string | `str` | `STATIC` or `DYNAMIC` (via GVRP). Only present when `family=1`. |
| tagged_ports | 3 | port-list | `str` | `|`-separated ranges, e.g. `7-8|11-14`. `None` when empty. |
| gvrp_ports | 4 | port-list | `str` | Same encoding. Only present when `family=1`. |
| untagged_ports | 5 | port-list | `str` | Same encoding. |
| forbid_ports | 6 | port-list | `str` | Same encoding. |
| auto_ports | 7 | port-list | `str` | Same encoding. Only present when `family=1`. |

## Example request

```
GET /cgi/getVLANAll HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getVLANAll.response.txt` (live-captured
2026-04-23, 80 bytes).

Excerpt:
```
1~DEFAULT_VLAN (Primary)~STATIC~None~None~7-8,11-14,17-24, Dyn1-Dyn3~None~None
```

(After the applet-side `|`→`,` substitution, the raw wire form uses
`|`. Our 2810 has only one VLAN so the fixture shows a single row.)

## Pydantic sketch

```python
from pydantic import BaseModel


class VlanRow(BaseModel):
    vlan_id: int
    vlan_name: str
    vlan_type: str                # STATIC | DYNAMIC
    tagged_ports: str             # "None" or pipe-separated list
    gvrp_ports: str
    untagged_ports: str
    forbid_ports: str
    auto_ports: str


class GetVlanAllResponse(BaseModel):
    vlans: list[VlanRow]
```

## Notes & caveats

- **No sentinel.** Unlike `listVLANS` (which prefixes a line with
  `OK~` on some views), `getVLANAll` streams raw data lines with no
  leading token. Phase 1 must not assume an `OK~` prefix on this
  endpoint.
- **Port-list encoding.** Raw wire uses `|` between ranges; the
  Java applet only converts to `,` for on-screen display. The
  Python parser should accept `|` as the canonical delimiter and
  not rely on any substitution.
- **`family` affects field count.** The `family=2` (Alpha) and
  `family=1` (Infinity) variants emit 8 fields; `family=0` (Voyager)
  skips `vlan_type`, `gvrp_ports`, `auto_ports` → 5 fields. Our 2810
  is `family=1` per the applet param.
</content>
</invoke>