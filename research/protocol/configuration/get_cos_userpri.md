# get_cos_userpri

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java` (generic list applet).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_user1.html:20-25`
(`<applet code=GenericList.class name=addrlist>` with
`<param name=dataURL value="../cgi/cosuser">`,
`<param name=titles value="Device Address~DSCP Policy~802.1p Priority">`,
`<param name=columns value="100~250~250">`,
`<param name=params value=".~.~.~.">`,
`<param name=onlyOneSelection value="1">`).
Sub-tab key: `qos` / `ippr` (Device Priority).

> **⚠ Ground-truth gap (audit F2, 2026-07-15):** this doc cites one or more
> `cos_*.html` mirror pages that are **not present** in
> `research/mirror/2026-04-23/configuration/` (only `cos_mainf.html` and
> `cos_menu.html` were captured; the per-subtab QoS pages were never
> mirrored and are not in git history). HTML-derived claims below are
> therefore unverifiable in-repo. Treat the wire contract as
> **experimental** until the QoS pages are re-mirrored or live-captured.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/cosuser`
- **Query params:** none.
- **Response body:** plain text, LF-separated, tilde-delimited
  rows. No sentinel. Zero or more rows; one per configured
  per-device QoS entry.

  Row shape:
  ```
  <ip_address>~<dscp_policy>~<priority>
  ```
  - `ip_address` — dotted-quad IPv4.
  - `dscp_policy` — `Disabled` or a 6-bit binary string.
  - `priority` — `No override` or a priority label.

- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| ip_address | 0 | dotted-quad IPv4 | `IPv4Address` | |
| dscp_policy | 1 | string | `str` | `Disabled` or `000000`..`111111`. |
| priority | 2 | string | `str` | `No override` or e.g. `0-Normal Priority`. |

## Example request

```
GET /cgi/cosuser HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_cos_userpri.response.txt` (live-captured
2026-04-23, 1 byte — empty list: no device-priority entries
configured).

## Pydantic sketch

```python
from ipaddress import IPv4Address
from pydantic import BaseModel


class CosUserEntry(BaseModel):
    ip_address: IPv4Address
    dscp_policy: str
    priority: str


class CosUserList(BaseModel):
    entries: list[CosUserEntry]
```

## Notes & caveats

- **Empty-list response.** Same pattern as `get_cos_appt`: single
  byte (just a newline) when no entries are configured.
- **Companion write:** `set_cos_userpri` (`/cgi/cosuserf`).
