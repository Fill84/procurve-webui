# get_diffserv

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java`.
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_tosds.html:11-16`
(`<applet code=GenericList.class name=prlist>` with
`<param name=dataURL value="../cgi/diffserv_get">`,
`<param name=titles value="Inbound DiffServ%Codepoint~DSCP Policy~802.1p Priority">`,
`<param name=columns value="110~250~250">`,
`<param name=params value=".~.~.">`,
`<param name=onlyOneSelection value="1">`).
Sub-tab key: `qos` / `tosds` (DiffServe TOS).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/diffserv_get`
- **Query params:** none.
- **Response body:** plain text, LF-separated, tilde-delimited
  rows. No sentinel. 64 rows (one per inbound codepoint 0..63).

  Row shape:
  ```
  <row_index>~<inbound_codepoint>~<dscp_policy>~<priority_label>
  ```
  - `row_index` — 1..64 (echoed as `indeces` on write).
  - `inbound_codepoint` — 6-bit binary of the inbound DSCP value.
  - `dscp_policy` — `Disabled` or a rewrite DSCP codepoint string.
  - `priority_label` — `No override` or a priority string.

- **Success indicator:** HTTP 200 with 64 rows.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| row_index | 0 | integer | `int` | 1..64. |
| inbound_codepoint | 1 | string | `str` | Binary. |
| dscp_policy | 2 | string | `str` | `Disabled` or rewrite target codepoint. |
| priority_label | 3 | string | `str` | `No override` or priority. |

## Example request

```
GET /cgi/diffserv_get HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_diffserv.response.txt` (live-captured
2026-04-23, 1981 bytes; 64 rows).

Excerpt:
```
1~000000~Disabled~No override
2~000001~Disabled~No override
...
64~111111~Disabled~No override
```

## Pydantic sketch

```python
from pydantic import BaseModel


class DiffservEntry(BaseModel):
    row_index: int
    inbound_codepoint: str
    dscp_policy: str
    priority_label: str


class DiffservTable(BaseModel):
    rows: list[DiffservEntry]
```

## Notes & caveats

- **4-field rows, 3-title declaration.** Extra first column is the
  row_index. Same pattern as `get_cos_vlanpri`.
- **Companion write:** `set_diffserv` (`/cgi/diffserv_set`).
