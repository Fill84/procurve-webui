# get_dscptable

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_dscpt.html:9-14`
(`<applet code=GenericList.class name=prlist>` with
`<param name=dataURL value="../cgi/dscptable_get">`,
`<param name=titles value="DSCP Codepoint~802.1p Priority">`,
`<param name=columns value="130~290">`,
`<param name=params value="cp~pr">`,
`<param name=onlyOneSelection value="1">`).
Sub-tab key: `qos` / `dscpt` (DSCP Policy Table).

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
- **URL template:** `/cgi/dscptable_get`
- **Query params:** none.
- **Response body:** plain text, LF-separated, tilde-delimited
  rows. No sentinel. 64 rows (one per DSCP codepoint 0..63).

  Row shape:
  ```
  <row_index>~<codepoint>~<priority_label>
  ```
  - `row_index` — 1..64 (1-based row number; matches DSCP
    codepoint + 1).
  - `codepoint` — 6-bit binary string, e.g. `000000`.
  - `priority_label` — `No override` or a named priority string.

- **Success indicator:** HTTP 200 with 64 rows.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| row_index | 0 | integer | `int` | 1..64; also the internal `indeces` key on writes. |
| codepoint | 1 | string | `str` | Binary representation; `int(codepoint, 2)` recovers the numeric DSCP. |
| priority_label | 2 | string | `str` | `No override` or e.g. `0-Normal Priority`. |

## Example request

```
GET /cgi/dscptable_get HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_dscptable.response.txt` (live-captured
2026-04-23, 1405 bytes; 64 rows).

Excerpt:
```
1~000000~No override
2~000001~No override
3~000010~No override
...
64~111111~No override
```

## Pydantic sketch

```python
from pydantic import BaseModel


class DscpPolicy(BaseModel):
    row_index: int
    codepoint: str  # 6-bit binary
    priority_label: str

    @property
    def dscp(self) -> int:
        return int(self.codepoint, 2)


class DscpTable(BaseModel):
    rows: list[DscpPolicy]
```

## Notes & caveats

- **`params=cp~pr` drives the write key names.** The GenericList
  applet param `params=cp~pr` tells `ListPane` that on row-edit
  submit, the column at position 1 becomes `&cp=<value>` and the
  column at position 2 becomes `&pr=<value>` (ListPane.java:581-591).
  The wire keys `cp` / `pr` carry over into `set_dscptable`.
- **Companion write:** `set_dscptable` (`/cgi/dscptable_set`).
