# set_diffserv

**Tab:** configuration
**Kind:** write
**Source in applet:** `GenericList`/`ListPane` (row-edit submission
path).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_tosds.html:17`
(`<FORM name=tosds target=wrkpg action=../cgi/diffserv_set>`), with
the DSCP select at lines 20-85.
Sub-tab key: `qos` / `tosds`.

> **Re-mirrored 2026-07-15 (closes audit F2):** the QoS sub-pages are now
> captured in `research/mirror/2026-07-15/configuration/` (22 pages,
> including `cos_app1/5/5a.html` which no doc had cited). Verified against
> the live HTML: CGI endpoint paths, submitted-form field names, and every
> `<select>` value domain (dscp 0-63, 802.1p 0-7, `255` sentinel where
> offered, apply-policy 1-3, app id 0-58, ToS mode 1-3) match this doc and
> the implementation. Still open: the multi-frame submit orchestration —
> the plain HTML form for cosappf/cosuserf/cosvlanf carries only a subset
> of the documented params (sibling frames hold the rest in unsubmitted
> forms, e.g. both pickers in `cos_app5(.a).html` are named `pr`); the
> applet merged them at submit time (GenericList `params`/`indeces`
> mechanism). Response bodies remain uncaptured.

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
