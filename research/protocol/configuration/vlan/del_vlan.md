# delVLAN

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANAddRemovePanel.java:306-328`. URL built as
`"delVLAN?"` at line 309, then each selected VLAN ID is appended as
`"VLAN_ID=<id>"` at line 314 with `"&"` separators at line 316; the
final request has one `VLAN_ID` query parameter per VLAN to delete
(duplicate keys, not a comma-list). Dispatched via
`callURLwithUpdate` at `:321-323`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/delVLAN?VLAN_ID={id1}&VLAN_ID={id2}&VLAN_ID={id3}...`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer, **repeating** | yes, at least once | VLAN to delete. The key is repeated for each selected VLAN. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** same shape as `addVLAN` — either
  `OK~<refresh_payload>` on success or `<error_message>~<refresh_payload>`
  on failure. Parsed by `VLANAddRemovePanel.callURLwithUpdate`
  (`:175-238`).
- **Success indicator:** first token equals `OK` (case-insensitive).
- **Error indicators:** first token is any other value. Expected messages
  include attempts to delete the primary VLAN or a VLAN with active
  tagged members.

## Field reference

Request:

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| vlan_ids | `VLAN_ID` (repeating) | decimal integer | `list[int]` | `len >= 1`; each `1..4094` | Wire preserves the order of the user's MultiList selection. |

## Example request

Delete a single VLAN (byte-exact):

```
GET /cgi/delVLAN?VLAN_ID=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Delete multiple VLANs (duplicate-key style — **do not collapse to a
comma-list**):

```
GET /cgi/delVLAN?VLAN_ID=5&VLAN_ID=6&VLAN_ID=7 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Matches the Java exactly: `m_query = "delVLAN?"` then
`m_query += "VLAN_ID=" + id` in a loop with `&` separators between
entries.

## Example response

Prepared example only — no live test of this write operation.

Success:
```
OK~1~DEFAULT_VLAN (Primary)~
```

Error (attempt to delete DEFAULT_VLAN / primary):
```
Cannot delete primary VLAN~1~DEFAULT_VLAN (Primary)~
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field


class DelVlanRequest(BaseModel):
    vlan_ids: list[int] = Field(min_length=1)


class DelVlanResponse(BaseModel):
    ok: bool
    error_message: str | None = None
    vlans: list  # list[VlanRef] from list_vlans.md (refresh payload)
```

For `httpx` the correct call is:

```python
params = [("VLAN_ID", str(i)) for i in req.vlan_ids]
r = client.get("/cgi/delVLAN", params=params)
```

— using a list-of-tuples (not a dict) so the key is repeated rather
than last-write-wins.

## Notes & caveats

- **Duplicate-key pattern is load-bearing.** See
  `_conventions.md` → "Query-string quirks". Compressing the
  duplicate keys into `VLAN_ID=5,6,7` will silently break the
  switch: it will either ignore all but the last ID or reject the
  request (exact behaviour unknown — needs live capture).
- **Trailing `&` handling.** The Java code writes no trailing `&`
  (the loop at `:315-317` only inserts `&` between entries, not
  after the last). Python clients should emit the same.
- **Refresh payload.** As with `addVLAN`, the response body doubles
  as a `listVLANS`-style refresh. The applet's `MultiList` is
  cleared and repopulated from the tokens after the first `OK~` /
  error string.
</content>
</invoke>