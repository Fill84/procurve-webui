# addVLAN

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANAddRemovePanel.java:287` (URL built as
`"addVLAN?VLAN_ID=" + id + "&VLAN_NAME=" + URLEncoder.encode(name)`);
dispatched via `callURLwithUpdate` at `VLANAddRemovePanel.java:295-297`.
Response handler: `VLANAddRemovePanel.java:175-238` (`OK~` sentinel
repopulates the list; anything else becomes an error dialog).
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/addVLAN?VLAN_ID={vlan_id}&VLAN_NAME={vlan_name}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | New VLAN's 802.1Q ID. Max width in the form is 5 digits (TextField size 5 — `VLANAddRemovePanel.java:75`). |
| `VLAN_NAME` | URL-encoded string | yes | VLAN display name. Max 12 characters (KeyListener consumes further keystrokes at `VLANAddRemovePanel.java:140`). Spaces are rejected client-side (also line 140). The applet applies `URLEncoder.encode` with the platform default encoding, which emits `+` for spaces and `%XX` for other special characters. |

- **Request headers:** none beyond standard.
- **Request body:** none (GET only).
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. On success:
  ```
  OK~<vlan_id>~<vlan_name>~<vlan_id>~<vlan_name>~...
  ```
  — i.e. the `OK~` sentinel followed by an in-band refresh of the
  `listVLANS` payload. The applet uses this to repopulate its
  MultiList without a separate round-trip.

  On error:
  ```
  <message>~<vlan_id>~<vlan_name>~...
  ```
  — the first token is an error string (can contain `|` to indicate
  line breaks; the applet splits on `|` and joins with `\n` for the
  dialog, `VLANAddRemovePanel.java:207-212`). The remainder is still
  a listVLANS-style refresh payload.

- **Success indicator:** First token equals `OK` (case-insensitive,
  `VLANAddRemovePanel.java:197`).
- **Error indicators:** First token is anything else. Common messages
  observed in similar CGIs: `error~VLAN with this ID or name already exists`.

## Field reference

Request:

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| vlan_id | `VLAN_ID` | decimal integer | `int` | `1 <= x <= 4094` (802.1Q) | |
| vlan_name | `VLAN_NAME` | URL-encoded string | `str` | `len <= 12`, no `~`, no spaces | The applet rejects `~` client-side via `hasIllegalChars` (`VLANAddRemovePanel.java:289, 381-390`) with message `"There is an illegal character in VLAN name.  The ~ character is not allowed in VLAN name."`. |

Response: see `list_vlans.md` for the refresh payload shape.

## Example request

For VLAN_ID=20, VLAN_NAME=`Guest` (byte-exact):

```
GET /cgi/addVLAN?VLAN_ID=20&VLAN_NAME=Guest HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

For a name with a space like `Guest+Net` (spaces are blocked by the
applet but `+` is legal):

```
GET /cgi/addVLAN?VLAN_ID=20&VLAN_NAME=Guest%2BNet HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

(Note: the wire encoding of literal `+` is `%2B`. The applet uses
`URLEncoder.encode` which encodes `+` → `%2B` and space → `+` — but
since spaces are blocked client-side, spaces shouldn't appear.)

## Example response

Prepared example only — no live test of this write operation.

Success:
```
OK~1~DEFAULT_VLAN (Primary)~20~Guest~
```

Error (duplicate):
```
VLAN with this ID already exists~1~DEFAULT_VLAN (Primary)~
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field, field_validator


class AddVlanRequest(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)
    vlan_name: str = Field(min_length=1, max_length=12)

    @field_validator("vlan_name")
    @classmethod
    def no_tilde_no_space(cls, v: str) -> str:
        if "~" in v:
            raise ValueError("VLAN name cannot contain '~'")
        if " " in v:
            raise ValueError("VLAN name cannot contain spaces")
        return v


class AddVlanResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    vlans: list  # list[VlanRef] from list_vlans.md
```

## Notes & caveats

- **Client-side validation preserved.** `~` and space are both
  rejected before the request is built, so a well-behaved client
  never sends them. The switch's behaviour for malformed input
  is **unknown — needs live capture** (we don't live-test writes).
- **`URLEncoder.encode` default charset.** Java 1.3-era
  `URLEncoder.encode(String)` uses the platform default charset
  (usually `UTF-8` on modern JVMs, but technically undefined).
  `httpx.QueryParams` with a `str` value will URL-encode using
  UTF-8, producing byte-identical results for the ASCII-safe
  12-character names the applet allows.
- **Response doubles as a refresh.** The applet's `callURLwithUpdate`
  reuses the response body to reset its MultiList regardless of
  success/failure. Python clients can ignore the refresh payload
  and separately call `listVLANS` if needed.
</content>
</invoke>