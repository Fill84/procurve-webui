# download_config

**Tab:** backup
**Kind:** read
**Source in applet:** none — this endpoint is a CGI, not an applet URL. The
`configuration/configfileSingle.html` HTML form is the only reference.
**Source in HTML:** `research/mirror/2026-04-23/configuration/configfileSingle.html`

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/configfile?idx={idx}&fg={fg}&D1=Download`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | idx | int | yes | Config slot index. 1 = Primary, 2 = Secondary. |
  | fg  | int | yes | Selected config file. In the default UI the JS copies `idx` into `fg` on submit, so they match. |
  | D1  | literal `Download` | yes | Form submit-button name. Distinguishes download from delete. |

- **Request headers:** none beyond standard (`Host`, `Accept`).
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | `application/octet-stream; file="CONFIG.pcc"` | Note the unusual `file=` Content-Type parameter. |
  | Content-Disposition | `attachment; filename="CONFIG.pcc"` | |

- **Response body:** ASCII text with CRLF line terminators, same syntax as
  `show running-config` on the CLI. Starts with
  `; J9021A Configuration Editor; Created on release #<firmware>`.
  Ends after the last configuration line.
- **Success indicator:** HTTP 200 with Content-Type containing
  `application/octet-stream`. A 200 with `text/html` means the form was
  misinterpreted as a menu page — retry with explicit `D1=Download`.
- **Error indicators:** Non-200 HTTP; `text/html` response body.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| slot | `idx` | int in querystring | `ConfigSlot` (IntEnum: PRIMARY=1, SECONDARY=2) | 1 or 2 | |
| fg | `fg` | int in querystring | mirrors slot | must equal `idx` | JS enforces equality before submit |
| action | `D1` | literal | constant `"Download"` | | form submit-button name |

## Example request

```
GET /cgi/configfile?idx=1&fg=1&D1=Download HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/download_config.response.txt` (live-captured
2026-04-23, 2904 bytes, SHA256
`f9234e4f9e1caa40fe4ea84ae008128a990e96462f4bfb360649f9746df98e11`).

Excerpt:
```
; J9021A Configuration Editor; Created on release #N.11.78

hostname "HP2810_01"
snmp-server contact "Phillippe Pelzer"
...
```

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel


class ConfigSlot(IntEnum):
    PRIMARY = 1
    SECONDARY = 2


class DownloadConfigRequest(BaseModel):
    slot: ConfigSlot = ConfigSlot.PRIMARY


class ConfigBackup(BaseModel):
    text: str
    size: int
    sha256: str
```

## Notes & caveats

- The raw response text is both a human-readable snapshot AND the exact
  payload used to restore via `upload_config` (see `upload_config.md`).
  Round-trip fidelity MUST be preserved — do not normalize line endings,
  do not strip whitespace.
- Submitting the form without `D1=Download` returns a confirmation HTML
  page instead of the file. The submit-button name is the CGI's only
  action discriminator.
- Blank switch creds: the current switch accepts requests without any
  `Authorization` header. When the user later sets manager credentials,
  this endpoint will 401 without Basic-auth.
