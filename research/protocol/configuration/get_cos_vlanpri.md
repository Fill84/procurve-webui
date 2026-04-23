# get_cos_vlanpri

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java` (generic list applet).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_vlan0.html:10-15`
(`<applet code=GenericList.class name=vlanlist>` with
`<param name=dataURL value="../cgi/cosvlan">`,
`<param name=titles value="VLAN Name (Vlan ID)~DSCP Policy~802.1p Priority">`,
`<param name=columns value="150~250~350">`,
`<param name=params value=".~.~.~.">`,
`<param name=onlyOneSelection value="1">`).
Sub-tab key: `qos` / `vlanPriority` (VLAN Priority).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/cosvlan`
- **Query params:** none.
- **Response body:** plain text, LF-separated, tilde-delimited
  rows. No sentinel. One row per VLAN.

  Row shape (observed):
  ```
  <vlan_id>~<vlan_label>~<dscp_policy>~<priority>
  ```
  - `vlan_id` — integer.
  - `vlan_label` — string combining name and ID, e.g.
    `DEFAULT_VLAN(1)`.
  - `dscp_policy` — `Disabled` or DSCP codepoint string.
  - `priority` — `No override` or a priority label.

- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| vlan_id | 0 | integer | `int` | |
| vlan_label | 1 | string | `str` | `<name>(<id>)` composite. |
| dscp_policy | 2 | string | `str` | |
| priority | 3 | string | `str` | |

## Example request

```
GET /cgi/cosvlan HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_cos_vlanpri.response.txt` (live-captured
2026-04-23, 40 bytes).

Content:
```
1~DEFAULT_VLAN(1)~Disabled~No override
```

## Pydantic sketch

```python
from pydantic import BaseModel


class CosVlanEntry(BaseModel):
    vlan_id: int
    vlan_label: str
    dscp_policy: str
    priority: str


class CosVlanList(BaseModel):
    entries: list[CosVlanEntry]
```

## Notes & caveats

- **4-field row against 3-title declaration.** The titles in
  cos_vlan0.html list three columns but the wire emits four — the
  applet treats the first two tokens as "row identity" (VLAN ID
  is the row key, the rendered label is the rest). Same pattern
  as `get_ports`' 10-field rows against its 8 title columns.
- **Companion write:** `set_cos_vlanpri` (`/cgi/cosvlanf`).
