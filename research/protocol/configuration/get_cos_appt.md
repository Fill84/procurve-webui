# get_cos_appt

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java` (generic list applet — same
as `get_ports`, `get_portscfg`, etc.).
**Source in HTML:** `research/mirror/2026-04-23/configuration/cos_app2.html:3-8`
(`<applet code=GenericList.class name=applist>` with
`<param name=dataURL value="../cgi/cosapp">`,
`<param name=titles value="Application~Application Port~Type~DSCP Codepoint~802.1p Priority">`,
`<param name=columns value="160~300~400~520~630">`,
`<param name=params value=".~.~.~.~.">`).
The cos_app2 frame is embedded from `cos_appf.html` via the QoS
menu (`cos_menu1.html` — not mirrored; served dynamically from the
switch — selects `cos_menu3.html?ldPage=7`, which JS-redirects to
`cos_appf.html`). Sub-tab key in menu: `qos` (menu.html:43),
sub-panel key: `appt` (Application Type).

> **⚠ Ground-truth gap (audit F2, 2026-07-15):** this doc cites one or more
> `cos_*.html` mirror pages that are **not present** in
> `research/mirror/2026-04-23/configuration/` (only `cos_mainf.html` and
> `cos_menu.html` were captured; the per-subtab QoS pages were never
> mirrored and are not in git history). HTML-derived claims below are
> therefore unverifiable in-repo. Treat the wire contract as
> **experimental** until the QoS pages are re-mirrored or live-captured.

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/cosapp`
- **Query params:** none.
- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response body:** plain text, LF-separated, tilde-delimited
  rows. No sentinel. Zero or more rows; one per configured
  application-priority entry.

  Declared columns (cos_app2.html:5):
  `Application~Application Port~Type~DSCP Codepoint~802.1p Priority`.
  Row shape:
  ```
  <application_name>~<port_number>~<type>~<dscp>~<priority>
  ```
  - `application_name` — e.g. `http (80)`, `User defined`.
  - `port_number` — TCP/UDP port.
  - `type` — `TCP` or `UDP`.
  - `dscp` — DSCP codepoint binary (e.g. `000000`), or a hyphen
    when no DSCP override.
  - `priority` — `No override` or an 802.1p value label.

- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire position | wire type | python type | notes |
|---|---|---|---|---|
| application_name | 0 | string | `str` | Human label with port suffix. |
| port_number | 1 | decimal integer | `int` | |
| type | 2 | `TCP`/`UDP` | `Literal` | |
| dscp | 3 | 6-bit binary string or `-` | `str` | Raw label; parse DSCP separately. |
| priority | 4 | string | `str` | `No override` when unset. |

## Example request

```
GET /cgi/cosapp HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_cos_appt.response.txt` (live-captured
2026-04-23, 1 byte — empty list on this switch: no application-
priority entries have been configured).

## Pydantic sketch

```python
from pydantic import BaseModel


class CosAppEntry(BaseModel):
    application_name: str
    port_number: int
    type: str  # TCP or UDP
    dscp: str
    priority: str


class CosAppList(BaseModel):
    entries: list[CosAppEntry]
```

## Notes & caveats

- **Empty-list response.** When no entries are configured, the CGI
  returns a single-byte response (just `\n`). Callers must tolerate
  zero-row responses. Row shape above is derived from the
  GenericList title/column params; actual row format is unverified
  on this switch because the list is empty.
- **Companion write:** `set_cos_appt` (`/cgi/cosappf`).
- **Application defaults** (the form's `<select>` in
  `cos_app3.html`) come from a hard-coded JS array of ~58 services
  — they are not fetched from the switch. Python need not fetch
  them either.
