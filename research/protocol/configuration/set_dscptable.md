# set_dscptable

**Tab:** configuration
**Kind:** write
**Source in applet:** `GenericList`/`ListPane` (the row-edit
submission path). `ListPane.java:620-646` (`submitForm()` assembles
`formURL + "?indeces=" + row_id + "&cp=..." + "&pr=..."`).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_dscpt.html:18`
(`<form name=dscppr target=wrkpg action=../cgi/dscptable_set>`).
The priority `<select name=pr>` at lines 21-30. There is no
`cp` input — the codepoint is implicit in the selected row
(echoed via `indeces`).
Sub-tab key: `qos` / `dscpt`.

> **⚠ Ground-truth gap (audit F2, 2026-07-15):** this doc cites one or more
> `cos_*.html` mirror pages that are **not present** in
> `research/mirror/2026-04-23/configuration/` (only `cos_mainf.html` and
> `cos_menu.html` were captured; the per-subtab QoS pages were never
> mirrored and are not in git history). HTML-derived claims below are
> therefore unverifiable in-repo. Treat the wire contract as
> **experimental** until the QoS pages are re-mirrored or live-captured.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/dscptable_set?indeces={row_index}&pr={0-7|255}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer 1..64 | yes | Row index selected in the GenericList (not the DSCP codepoint directly; row index = codepoint + 1). Source: ListPane.java:625. |
  | pr | 0..7 or 255 | yes | Priority mapping for the selected codepoint. `255` = No Override. Source: cos_dscpt.html:21-30. |

- **Request body:** none (GET).
- **Response body:** **not live-tested.**

## Field reference

| field | wire key | wire type | python type | notes |
|---|---|---|---|---|
| row_index | `indeces` | integer | `int` | 1..64. |
| priority_8021p | `pr` | integer | `int` | 0..7 or 255 for "No Override". |

## Example request

Map DSCP codepoint 46 (101110, row_index 47) to 802.1p priority 5:
```
GET /cgi/dscptable_set?indeces=47&pr=5 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Clear the mapping (no override) for codepoint 46:
```
GET /cgi/dscptable_set?indeces=47&pr=255 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, Field


class SetDscpTableRequest(BaseModel):
    row_index: int = Field(ge=1, le=64)
    priority_8021p: int  # 0..7 or 255
```

## Notes & caveats

- **Row index vs codepoint.** The row is 1-based; DSCP codepoint
  is 0-based. `row_index = codepoint + 1`. Python helpers should
  offer both; the wire requires the 1-based value.
- **`cp` column is read-only.** Writes never change the codepoint
  column — only the priority.
- **Related:** `get_dscptable`.
