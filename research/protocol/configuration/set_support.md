# set_support

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/support.html:65`
(`<form name=si action="../cgi/support" onSubmit="return doSubmit();">`),
with hidden `indeces=0` (line 66), `_SuppURL` (line 71),
`hpHttpMgMgmtSrvrURL` (line 75). Frameset entry:
`research/mirror/2026-04-23/configuration/supportf.html:3`.
Sub-tab key: `support` (menu.html:49).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/support?indeces=0&_SuppURL={support_url}&hpHttpMgMgmtSrvrURL={mgmt_url}&apply=+Apply+Changes+`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | literal `0` | yes | Hidden field (support.html:66). |
  | _SuppURL | URL string (0-103 chars) | yes | User-facing support URL. Note the underscore prefix. |
  | hpHttpMgMgmtSrvrURL | URL string (0-103 chars) | yes | Management-server URL (automatic-management target). |
  | apply | literal `" Apply Changes "` | submit button value | Preserve byte-exactly. |

  Char whitelist (enforced by `doSubmit()` at support.html:39):
  ```
  /^[a-z|A-Z|0-9|`|!|@|#|\$|%|\^|&|\*|\(|\)|_|\+|=|\{|\}|\||\\|\]|\[|"|:|\;|'|\?|>|<|,|\.|\/| |-]+$/
  ```
  Same whitelist as system-info (minus `~`) except the quantifier
  is `+` (at least one char) rather than `*` (zero+). An empty
  URL is therefore rejected client-side; the Python validator
  should mirror.

  Max length: 103 chars per field (support.html:34: `maxLen = 103`).

- **Request body:** none (GET).
- **Response body:** **not live-tested.** Expected `OK~...` or an
  HTML redirect.
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| support_url | `_SuppURL` | URL string | `HttpUrl \| str` | 1-103 chars, char whitelist | Shown to users who click "Support" in the UI. |
| mgmt_url | `hpHttpMgMgmtSrvrURL` | URL string | `HttpUrl \| str` | 1-103 chars, char whitelist | Used by the "check for auto-management" warnings (e.g. cos_menu.html:6-14). |
| apply | `apply` | literal | str | exact | Submit button value. |

## Reading the current value

No dedicated read CGI. The live URLs are injected into
support.html:
- `<input name=_SuppURL value="http://www.procurve.com" size=48>` (line 71)
- `<input name=hpHttpMgMgmtSrvrURL value="https://www.hpe.com/networking/support" size=48>` (line 75)

A Python scraper must GET `/configuration/support.html` and regex-
match the `value="..."` attributes. Same HTML-scrape pattern as
`set_system_info.md`.

## Example request

```
GET /cgi/support?indeces=0&_SuppURL=http%3A%2F%2Fwww.procurve.com&hpHttpMgMgmtSrvrURL=https%3A%2F%2Fwww.hpe.com%2Fnetworking%2Fsupport&apply=+Apply+Changes+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, Field


SUPPORT_FIELD_REGEX = (
    r"^[A-Za-z0-9`!@#\$%\^&\*\(\)_\+=\{\}\|\\\]\[\":;'\?><,\./ -]+$"
)


class SetSupportRequest(BaseModel):
    support_url: str = Field(min_length=1, max_length=103, pattern=SUPPORT_FIELD_REGEX)
    mgmt_url: str = Field(min_length=1, max_length=103, pattern=SUPPORT_FIELD_REGEX)
```

## Notes & caveats

- **No `~`.** Same reason as system-info: `~` is the switch's
  response delimiter.
- **Character set.** The JS regex allows spaces and most ASCII
  punctuation but notably excludes `~`. Python validation must
  enforce this exactly.
- **`ncidbar` refresh.** The page's `reloadFrame()`
  (support.html:30-32) reloads `../ncidbar.html` after submit —
  because the banner's click-through reads a URL from the
  management-server field. Python clients need not re-issue a
  banner GET.
- **Related:** `set_system_info` (same form pattern).
