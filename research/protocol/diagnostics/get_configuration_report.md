# get_configuration_report

**Tab:** diagnostics
**Kind:** read
**Source in applet:** none — this is a server-rendered HTML page, not an
applet-driven CGI.
**Source in HTML:** `research/mirror/2026-04-23/diagnostics/config.html` (the
page itself is the report).
**Frame wrapper:** `research/mirror/2026-04-23/diagnostics/configf.html`.

## HTTP contract

- **Method:** GET
- **URL template:** `/diagnostics/config.html`
- **Query params:** none.
- **Request headers:** standard.
- **Request body:** none.
- **Response headers (relevant):**

  | header | value | notes |
  |---|---|---|
  | Content-Type | `text/html` | report is embedded in `<pre>` inside an HTML page |

- **Response body:** an HTML page whose `<pre>...</pre>` block contains the complete running-config in CLI syntax. The config block is byte-equivalent to the body of `/cgi/configfile?idx=1&fg=1&D1=Download` modulo the surrounding HTML. Leading 3-line preamble:

  ```
  <font face="Helvetica" size=0>
  <b>You may wish to use your browser to print the following report or to save it into a file.</b></font><hr>
  <pre>
  ; J9021A Configuration Editor; Created on release #N.11.78

  hostname "HP2810_01"
  ...
  ```

- **Success indicator:** HTTP 200 with `text/html`.
- **Error indicators:** HTTP 401 if a manager password is set and auth is missing.

## Field reference

Single string field; structured parsing is done by the CLI-config
extractor (shared with `backup/download_config`).

| field | source | python type | notes |
|---|---|---|---|
| raw_html | response body | `str` | |
| config_text | regex-extract from `<pre>...</pre>` | `str` | the same text `download_config` returns |

## Example request

```
GET /diagnostics/config.html HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/diagnostics__get_configuration_report.response.txt`
(live-captured 2026-04-23, 3923 bytes, SHA256
`13b4a54bdff921644cf26aeb7c7b1e0b05f6ad2411fcd3f48b08f9d2788aafc5`).

Excerpt:
```
<pre>
; J9021A Configuration Editor; Created on release #N.11.78

hostname "HP2810_01"
snmp-server contact "Phillippe Pelzer"
...
```

## Pydantic sketch

```python
from pydantic import BaseModel


class ConfigurationReport(BaseModel):
    raw_html: str
    config_text: str  # extracted from <pre>...</pre>
```

## Notes & caveats

- This operation duplicates `backup/download_config` in intent but differs in wire shape. For backup purposes use the `/cgi/configfile?…&D1=Download` binary-download path (it returns `application/octet-stream` with a proper `Content-Disposition` filename). For a human-readable view embedded in the UI, this HTML report is easier to render.
- The `<pre>` contents preserve CLI line endings (CRLF on wire). Do not normalize when feeding into a diff view.
- Round-trip fidelity: the body inside `<pre>` is NOT guaranteed byte-identical to the `download_config` output — the HTML rendering layer may HTML-escape `<`, `>`, `&` in config strings (e.g., in passwords or SNMP community strings). The new UI should use `download_config` for restore workflows and reserve this endpoint for preview-only use.
