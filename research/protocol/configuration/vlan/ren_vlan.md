# renVLAN

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANAddRemovePanel.java:330-355`. URL built as
`"renVLAN?"` at line 333; `VLAN_ID=<id>` appended at line 338;
`&VLAN_NAME=` + `URLEncoder.encode(newName)` at line 339. Dispatched
via `callURLwithUpdate` at `:347-349`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/renVLAN?VLAN_ID={vlan_id}&VLAN_NAME={vlan_name}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | VLAN to rename. Must already exist. |
| `VLAN_NAME` | URL-encoded string | yes | New name. Same 12-char / no-tilde / no-space constraints as `addVLAN`. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** `OK~<refresh>` or `<error>~<refresh>` — same
  shape as `addVLAN` / `delVLAN` (parsed by
  `callURLwithUpdate`).
- **Success indicator:** first token equals `OK` (case-insensitive).
- **Error indicators:** first token is any other value. The applet
  also pre-validates name collision client-side at
  `VLANAddRemovePanel.java:341-345` and raises `"VLAN with this ID or
  name already exists"` without hitting the wire.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| vlan_id | `VLAN_ID` | decimal integer | `int` | `1..4094` | |
| vlan_name | `VLAN_NAME` | URL-encoded string | `str` | `len <= 12`, no `~`, no space | Encoded with `URLEncoder.encode` (space → `+`, `+` → `%2B`). |

## Example request

Rename VLAN 20 to `Guests` (byte-exact):

```
GET /cgi/renVLAN?VLAN_ID=20&VLAN_NAME=Guests HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Prepared example only — no live test of this write operation.

Success:
```
OK~1~DEFAULT_VLAN (Primary)~20~Guests~
```

Error:
```
VLAN with this ID or name already exists~1~DEFAULT_VLAN (Primary)~20~Guest~
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field, field_validator


class RenVlanRequest(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)
    vlan_name: str = Field(min_length=1, max_length=12)

    @field_validator("vlan_name")
    @classmethod
    def no_tilde_no_space(cls, v: str) -> str:
        if "~" in v or " " in v:
            raise ValueError("VLAN name cannot contain '~' or space")
        return v


class RenVlanResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    vlans: list  # list[VlanRef] (refresh payload)
```

## Notes & caveats

- **Only the first selected VLAN is renamed.** The Java code iterates
  `selectedPorts()` but only uses index 0 inside an `if` (not a
  `while`), `VLANAddRemovePanel.java:334-340`. Multi-select rename is
  not supported by the applet and shouldn't be exposed in the Python
  client either.
- **Refresh payload.** Same as `addVLAN` / `delVLAN`: the response
  body acts as a free `listVLANS` update.
</content>
</invoke>