# set_diffserv

**Tab:** configuration
**Kind:** write
**Source in applet:** `GenericList`/`ListPane` (row-edit submission
path).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_tosds.html:17`
(`<FORM name=tosds target=wrkpg action=../cgi/diffserv_set>`), with
the DSCP select at lines 20-85.
Sub-tab key: `qos` / `tosds`.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/diffserv_set?indeces={row_index}&dscp={0-63|255}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer 1..64 | yes | Row index selected in the GenericList (row_index = inbound_codepoint + 1). |
  | dscp | 0..63 or 255 | yes | Rewrite DSCP codepoint. `255` = Disabled. Source: cos_tosds.html:20. |

- **Request body:** none (GET).
- **Response body:** **not live-tested.**

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| row_index | `indeces` | integer | `int` | 1..64. |
| dscp | `dscp` | integer | `int` | 0..63 or 255. |

## Example request

Rewrite inbound DSCP 10 (row_index 11) to DSCP 46:
```
GET /cgi/diffserv_set?indeces=11&dscp=46 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Disable rewrite for inbound DSCP 10:
```
GET /cgi/diffserv_set?indeces=11&dscp=255 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, Field


class SetDiffservRequest(BaseModel):
    row_index: int = Field(ge=1, le=64)
    dscp: int  # 0..63 or 255
```

## Notes & caveats

- **Only the DSCP column is editable.** The priority (802.1p) is
  not carried on this write — it's derived from the DSCP policy
  itself elsewhere, or kept at its existing value. **Needs live
  capture** to confirm priority is preserved after a dscp edit.
- **Related:** `get_diffserv`, `set_dscptable`.
