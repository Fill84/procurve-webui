# read_identity_page

**Tab:** identity
**Kind:** read
**Source in applet:** none — the Identity tab is a pure-static HTML page; no applet and no CGI are involved.
**Source in HTML:** `research/mirror/2026-04-23/identity/index.html` (frameset), `research/mirror/2026-04-23/identity/identity.html` (content frame).

## HTTP contract

- **Method:** GET
- **URL template:** `/identity/identity.html`
- **Query params:** none.
- **Request headers:** none beyond standard (`Host`, `Accept`).
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | `text/html` | rendered by the browser, not an applet. |

- **Response body:** HTML page containing an inline `<script>` block that
  builds a `page` variable via string concatenation and calls
  `document.write(page)` (identity.html:74-143). All displayed identity
  values are already baked into the HTML at page-render time by the
  switch's template engine; no runtime CGI call is made after the page
  loads. Values live inside the JS string literals between
  `<font face=Helvetica size=-1>` and `</font>` tags.

  The fields are (in file order, identity.html:85-137):
  - **System Name** — hostname (identity.html:86).
  - **System Location** — SNMP sysLocation (identity.html:90).
  - **System Contact** — SNMP sysContact (identity.html:94).
  - **System Up-Time** — centiseconds (hundredths of a second) passed to
    the `ft()` helper at identity.html:34-57 which formats them as
    `"<d> days, <h> hours, <m> minutes, <s> seconds"`. The raw value is
    the literal passed to `ft(...)` (identity.html:98).
  - **System CPU Util(%)** — integer percent (identity.html:103).
  - **System Memory** — two values concatenated into a single cell:
    `Total - <bytes>` and `Free - <bytes>` (identity.html:108-109).
  - **Product** — marketing name + part number, e.g.
    `ProCurve Switch 2810-24G (J9021A)` (identity.html:115-116).
  - **Base MAC Address** — space-separated lower-case hex octets
    (identity.html:120). Note trailing spaces.
  - **Serial Number** — string, trailing spaces preserved
    (identity.html:125).
  - **Version** — firmware + ROM, e.g. `N.11.78, ROM N.10.01`
    (identity.html:130).
  - **IP Address** — management IPv4 (identity.html:134).
  - **Management Server** — URL (rendered by `link()` at
    identity.html:65-68 which wraps non-empty URLs in an `<a>` tag or
    emits `(None)` otherwise).

- **Success indicator:** HTTP 200 with `text/html` body containing the
  marker string `System Name:` (identity.html:84).
- **Error indicators:** Non-200 HTTP; missing marker string; body does
  not contain `document.write( page )`.

## Field reference

| field | wire key (JS literal) | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| system_name | `System Name:` cell | free-form string | `str` | strip trailing whitespace | hostname |
| system_location | `System Location:` cell | free-form string | `str` | strip trailing whitespace | SNMP sysLocation |
| system_contact | `System Contact:` cell | free-form string | `str` | strip trailing whitespace | SNMP sysContact |
| uptime_centiseconds | `ft("...")` argument | decimal integer as string | `int` | `>= 0` | centiseconds since boot; the `ft()` helper divides by 100 first |
| cpu_pct | `System CPU Util(%):` cell | integer as string | `int` | `0..100` | |
| memory_total | `Total - <n>` inside `System Memory:` cell | decimal integer | `int` | `>= 0` | bytes |
| memory_free | `Free - <n>` inside `System Memory:` cell | decimal integer | `int` | `>= 0` | bytes |
| product | `Product:` cell | two lines joined: marketing name + `(part_no)` | `str` | | e.g. `"ProCurve Switch 2810-24G (J9021A)"` |
| base_mac | `Base MAC Address:` cell | `hh hh hh hh hh hh` (space-separated lower-case hex) | `str` (or normalized MAC) | `^([0-9a-f]{2} ){5}[0-9a-f]{2}$` | trailing spaces present in source |
| serial_number | `Serial Number:` cell | free-form alnum | `str` | strip trailing whitespace | |
| firmware_version | `Version:` cell | `<fw>, ROM <rom>` | `str` (or split into two fields) | | leading whitespace present in source |
| ip_address | `IP Address:` cell | dotted-quad | `IPv4Address` | valid IPv4 | |
| management_server_url | `Management Server:` cell → `link(...)` arg | URL or empty string | `HttpUrl \| None` | `None` when empty (`link("")` returns `"(None)"`) | |

## Example request

```
GET /identity/identity.html HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/read_identity_page.response.txt` (live-captured
2026-04-23, 5009 bytes, SHA256
`fdc398eaa740a55f11739eece64cc9d6a14ff1c2d62d2182da09eab448032525`).

Excerpt (the relevant JS literals; full HTML in the fixture):
```
"   HP2810_01</font></td></tr> \n" +
"   Kamer</font></td></tr> \n" +
"   Phillippe Pelzer</font></td></tr> \n" +
        ft("3539965") +
"   ProCurve Switch 2810-24G" +
"   (J9021A)</font></td></tr> \n" +
"   00 1d b3 b7 0e 00  "+
"   CN814XI06X  " +
"    N.11.78, ROM N.10.01</font></td></tr> \n" +
"   192.168.178.3\n</td></tr>" +
```

## Pydantic sketch

```python
from ipaddress import IPv4Address
from pydantic import BaseModel, HttpUrl


class IdentityPage(BaseModel):
    system_name: str
    system_location: str
    system_contact: str
    uptime_centiseconds: int
    cpu_pct: int
    memory_total_bytes: int
    memory_free_bytes: int
    product: str
    base_mac: str
    serial_number: str
    firmware_version: str
    ip_address: IPv4Address
    management_server_url: HttpUrl | None = None
```

## Notes & caveats

- **No CGI endpoint for identity data.** The switch renders the whole
  page server-side with values interpolated into JS string literals.
  Scraping the HTML is the only way to get these fields via the web UI
  without SNMP or the CLI. A regex/HTML-parse extractor must handle
  the trailing whitespace the template leaves in several cells
  (`Base MAC Address`, `Serial Number`, `System Memory`).
- **Uptime precision.** The value is centiseconds (1/100 s), not
  milliseconds. `ft()` at identity.html:37 does `parseInt(ms/100)` —
  the parameter name `ms` is misleading; the switch feeds hundredths.
  For a running switch the value advances visibly between two fetches.
- **Memory cell has two numbers.** Parse `Total - <n>` and
  `Free - <n>` separately; do not assume a single integer. The source
  inserts them with trailing spaces to pad columns.
- **Management Server URL.** When the switch has no management URL
  configured, the `link()` helper emits the literal `(None)`. Treat
  that as `null` on the Python side.
- **Frameset entry point.** `/identity/index.html` is only a frameset;
  its sole content frame is `identity.html`. Fetching `index.html` and
  then following the `<frame src=...>` is unnecessary — fetch
  `identity.html` directly.
- **No auth header required today** (switch has blank manager creds);
  when creds are set, this page will 401 without Basic auth.
- **Nav tabs reference.** The top-level six-tab row in
  `research/mirror/2026-04-23/nctabs.html` maps
  `identity~Identity~../identity/index.html` — this is the entry the
  top nav uses, but the applet-less content frame is `identity.html`
  in the same directory.
