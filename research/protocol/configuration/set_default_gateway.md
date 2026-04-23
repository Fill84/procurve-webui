# set_default_gateway

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/ip1.html:57`
(`<form name=iprt action="../cgi/gateway" onSubmit="return ivalidate();">`),
with the single `rt` input (line 64) and a submit button (line 67).
Sub-tab key in menu: `ip` (menu.html:40) — same sub-tab as
`set_ip_config.md`, different CGI endpoint.

## HTTP contract

- **Method:** GET.
- **URL template:** `/cgi/gateway?rt={gateway}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | rt | IPv4 dotted-quad | yes | Default gateway. Empty value is rewritten to `0.0.0.0` by `ivalidate()` (ip1.html:43-47). Otherwise a client-side `IPvalidate()` call validates the address before submission (not shown in the mirrored HTML — inferred to be the standard dotted-quad check). |

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** **not live-tested.** Expected to be a short
  `OK~...` acknowledgement.
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| gateway | `rt` | dotted-quad IPv4 | `IPv4Address \| Literal["0.0.0.0"]` | strict IPv4 | `0.0.0.0` = clear the default gateway. |

## Reading the current value

Same as `set_ip_config.md` — no dedicated CGI. Scrape
`/configuration/ip1.html` for either the `defaultGateway` JS var
(line 31) or the `<input name=rt value="...">` attribute (line 64).

## Example request

```
GET /cgi/gateway?rt=192.168.178.1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Clear the default gateway:
```
GET /cgi/gateway?rt=0.0.0.0 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from ipaddress import IPv4Address
from pydantic import BaseModel


class SetDefaultGatewayRequest(BaseModel):
    gateway: IPv4Address  # wire key: rt


class SetDefaultGatewayResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Overlap with `set_ip_config`.** Both forms share the `rt` key.
  `/cgi/gateway` sets only the gateway; `/cgi/ip` sets gateway +
  VLAN + mode in one shot. The UI usually submits `/cgi/ip` (via
  the ip2 Apply button) and `/cgi/gateway` is only hit when the
  user clicks the dedicated Apply button on the gateway sub-frame.
  A Python client can pick whichever fits — prefer `set_ip_config`
  when changing multiple fields to avoid two round-trips.
- **No button value submitted.** The submit input is
  `<input type="submit" value="Apply">` with no `name=` attribute,
  so its value is not included in the query string. The request is
  literally just `?rt=<ip>`.
