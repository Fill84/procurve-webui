# getVLANPort

**Tab:** configuration (VLAN subsystem)
**Kind:** read
**Source in applet:** `VLANmodifyPanel.java:190` (called through
`VLANmain.callURL("getVLANPort?VLAN_ID=" + vlanId)`); logged at
`VLANmodifyPanel.java:191` as `/cgi/getVLANPort?VLAN_ID=`; parsed at
`VLANmodifyPanel.java:192-223`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/getVLANPort?VLAN_ID={vlan_id}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | VLAN to query. Must exist; on our 2810 only `1` (DEFAULT_VLAN) exists by default. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text, one line, tilde-delimited.

  Layout (`family=1`):
  ```
  <gvrp_enable>~<port_name>~<port_id>~<mode>~<port_name>~<port_id>~<mode>~...
  ```
  - `gvrp_enable` is `ON` or `OFF`. The applet uses this to decide
    whether the mode-choice dropdown shows `Auto` or `No` as the
    first per-port option (`VLANmodifyPanel.java:200-213`).
  - Trailing `~` terminator.

- **Success indicator:** HTTP 200 with body beginning with `ON` or
  `OFF`. There is no `OK~`/`error~` sentinel.
- **Error indicators:** Non-200; empty body; VLAN_ID not present
  on the switch (exact switch behaviour for unknown VLAN IDs is
  **unknown — needs live capture** with an invalid id; out of
  scope for this fixture-capture pass).

## Field reference

Leading sentinel:

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| gvrp_enable | 0 | `ON` / `OFF` | `bool` | Controls the mode dropdown's first label (Auto vs No). |

Per port record (positions offset from 1, in groups of 3):

| field | wire type | python type | notes |
|---|---|---|---|
| port_name | string | `str` | Display name: `1`..`24`, `Dyn1`..`Dyn3` on our 2810. |
| port_id | decimal integer | `int` | Internal port index. |
| mode | decimal integer | `int` | `0`=Auto/No, `1`=Tagged, `2`=Untagged, `3`=Forbid. See "Notes". |

## Example request

```
GET /cgi/getVLANPort?VLAN_ID=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/vlan__getVLANPort.response.txt` (live-captured
2026-04-23, 209 bytes; args `VLAN_ID=1`, the DEFAULT_VLAN).

Raw body:
```
OFF~1~1~0~2~2~0~3~3~0~4~4~0~5~5~0~6~6~0~7~7~2~8~8~2~9~9~0~10~10~0~11~11~2~...~Dyn1~73~2~Dyn2~74~2~Dyn3~75~2~
```

(Ports 7, 8, 11-14, 17-24 and Dyn1-Dyn3 show mode=2 (Untagged) —
they match the `untagged_ports` list from `getVLANAll`'s record for
VLAN 1.)

## Pydantic sketch

```python
from pydantic import BaseModel


class VlanPortMode(BaseModel):
    port_name: str
    port_id: int
    mode: int  # 0=Auto/No, 1=Tagged, 2=Untagged, 3=Forbid


class GetVlanPortResponse(BaseModel):
    vlan_id: int
    gvrp_enable: bool
    ports: list[VlanPortMode]
```

## Notes & caveats

- **Mode encoding.** The modify panel's Choice is
  `{" ", "Auto"/"No", "Tagged", "Untagged", "Forbid"}` for
  `family=1` (`VLANmodifyPanel.java:79-83`). Wire value is
  `selected_index - 1` (`MultiList.setModeForSelected`,
  MultiList.java:299), so: `Auto/No = 0`, `Tagged = 1`,
  `Untagged = 2`, `Forbid = 3`. When GVRP is ON the first-option
  label is "Auto" (and the applet calls `setGVRP(0)`); when OFF
  it is "No" (and `setGVRP(1)`). Same integer value either way.
- **Single-line body.** Unlike `getVLANAll`, the whole response is
  one tilde-delimited line; the parser iterates tokens in a flat
  stream.
- **Paired with `setVLANPort`.** See `set_vlan_port.md`.
</content>
</invoke>