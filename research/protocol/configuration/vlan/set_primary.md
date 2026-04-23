# setPrimary

**Tab:** configuration (VLAN subsystem)
**Kind:** write
**Source in applet:** `VLANAddRemovePanel.java:412-430`. URL built as
`"setPrimary?VLAN_ID=" + selectedIds[0]` at line 421, dispatched via
`VLANmain.callURL(...)`. Response is drained but not parsed — the
applet re-fetches via `getDataForList()` at line 429.
**Source in HTML:** `research/mirror/2026-04-23/configuration/vlan.html`
hosts the `VLANmain.class` applet with `basecgiurl=../cgi/`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/setPrimary?VLAN_ID={vlan_id}`
- **Query params:**

| name | type | required | description |
|---|---|---|---|
| `VLAN_ID` | decimal integer | yes | VLAN to promote to primary. Only the first-selected entry is used. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** not inspected.
- **Response body:** plain text. Expected `OK` / `OK~...` on success
  and `error~<message>` on failure (consistent with sibling VLAN
  write CGIs), but the applet does not inspect the body — it simply
  opens a `BufferedReader` and drops it when re-fetching the list.
  Exact error shape is **unknown — needs live capture**.
- **Success indicator:** HTTP 200. The applet trusts success and
  immediately calls `getDataForList()`.
- **Error indicators:** Non-200 HTTP or any body that `listVLANS`
  doesn't reflect after the refresh.

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| vlan_id | `VLAN_ID` | decimal integer | `int` | Must exist. |

## Example request

Byte-exact:

```
GET /cgi/setPrimary?VLAN_ID=20 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

Prepared example only — no live test of this write operation.

Expected success (by analogy with other VLAN write CGIs):
```
OK
```

## Pydantic sketch

```python
from pydantic import BaseModel, Field


class SetPrimaryRequest(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)


class SetPrimaryResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Single-selection only.** The applet uses `selectedIds[0]` and
  early-returns if the selection is empty (`VLANAddRemovePanel.java:414-417`).
- **Response is ignored by the applet.** `VLANAddRemovePanel.setPrimaryVLAN`
  doesn't read the body — it just calls `callURL` and then
  immediately re-fetches with `getDataForList()` to see the new
  `(Primary)` suffix on the VLAN name. So our Python client has
  to live-test this write to know the exact success/failure body
  format. Flag: **unknown — needs live capture**.
- **Effect visible in `getVLANAll`.** The primary VLAN's name gets a
  literal ` (Primary)` suffix (see the DEFAULT_VLAN row in the
  `getVLANAll` fixture).
</content>
</invoke>