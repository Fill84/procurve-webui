# set_system_info

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only.
**Source in HTML:** `research/mirror/2026-04-23/configuration/system.html:67`
(`<form name=si action="../cgi/system" onSubmit="return isOk();">`),
with the `indeces=0` hidden field (line 68), `sysName` (line 83),
`sysLocation` (line 89), and `sysContact` (line 95). Frameset entry:
`research/mirror/2026-04-23/configuration/systemf.html:3`.
Sub-tab key in menu: `system` (menu.html:41).

## HTTP contract

- **Method:** GET (HTML `<form>` defaults to GET when `method=` is
  unset; tab-wide convention).
- **URL template:** `/cgi/system?indeces=0&sysName={name}&sysLocation={location}&sysContact={contact}&apply=+Apply+Changes+`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | integer literal `0` | yes | Hidden field set at system.html:68. The switch expects it even though its value is always 0 on this page. |
  | sysName | string (1-30 chars) | yes | System name. Cannot be empty (system.html:36-40: "System Name can not be empty"). Max length 30 chars (line 53: `i == 1 ? 30 : 48`). |
  | sysLocation | string (0-48 chars) | yes | Physical location. Max length 48. |
  | sysContact | string (0-48 chars) | yes | Contact person / email. Max length 48. |
  | apply | literal `" Apply Changes "` (URL-encoded) | submit button name | Browsers include the submit button value; preserve for byte-exact replay. |

  Character whitelist (enforced client-side, system.html:32):
  ```
  /^[a-z|A-Z|0-9|`|!|@|#|\$|%|\^|&|\*|\(|\)|_|\+|=|\{|\}|\||\\|\]|\[|"|:|\;|'|\?|>|<|,|\.|\/| |-]*$/
  ```
  Python clients should enforce the same, or tolerate server-side
  rejection. The regex as written is printable ASCII plus space,
  minus literal `~` (which the switch uses as a field delimiter in
  responses).

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** **not live-tested.** Expected to be a short
  `OK~...` line or a redirect to a refreshed `system.html`. The
  page's `onSubmit` handler also triggers `ncidbar.location =
  ncidbar.location` (system.html:108) to refresh the banner because
  the banner displays the system name — i.e. the switch returns
  something the browser can re-navigate from.
- **Success indicator:** HTTP 200.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| indeces | `indeces` | literal `0` | `int = 0` | must be `0` | Hidden field; semantically meaningless on this page. |
| name | `sysName` | string | `constr(min_length=1, max_length=30)` | char whitelist | Required non-empty. |
| location | `sysLocation` | string | `constr(max_length=48)` | char whitelist | May be empty. |
| contact | `sysContact` | string | `constr(max_length=48)` | char whitelist | May be empty. |

## Reading the current value

No dedicated CGI. The live name/location/contact are injected by
the switch directly into `system.html`:
- `sysName` default at `<input name=sysName value="HP2810_01" size=32>` (system.html:83)
- `sysLocation` default at line 89
- `sysContact` default at line 95

Same pattern as `set_fault_detection.md`. A Python reader must GET
`/configuration/system.html` and regex-scrape the `value="..."`
attributes from the three `<input>` tags. The MAC address at
system.html:73 (`00 1d b3 b7 0e 00`) is also available via this
page as a read-only field — it has no separate CGI.

## Example request

```
GET /cgi/system?indeces=0&sysName=HP2810_01&sysLocation=Kamer&sysContact=Phillippe+Pelzer&apply=+Apply+Changes+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from pydantic import BaseModel, Field


SYSTEM_FIELD_REGEX = (
    r"^[A-Za-z0-9`!@#\$%\^&\*\(\)_\+=\{\}\|\\\]\[\":;'\?><,\./ -]*$"
)


class SetSystemInfoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30, pattern=SYSTEM_FIELD_REGEX)
    location: str = Field(max_length=48, pattern=SYSTEM_FIELD_REGEX)
    contact: str = Field(max_length=48, pattern=SYSTEM_FIELD_REGEX)

    # wire keys: sysName, sysLocation, sysContact; hidden indeces=0; apply=" Apply Changes "


class SetSystemInfoResponse(BaseModel):
    ok: bool  # inferred from HTTP status
```

## Notes & caveats

- **Spaces in the `apply` button value.** The browser URL-encodes
  the button's `value=" Apply Changes "` (with leading/trailing
  spaces). Matching byte-for-byte matters only if the CGI inspects
  the button. The switch most likely ignores it — but preserve it
  anyway for the byte-match test.
- **No tilde.** The client-side regex permits printable ASCII minus
  `~`. Omitting `~` is deliberate: the switch uses `~` as its
  response field delimiter, so letting user text contain one would
  corrupt subsequent reads. Python validation must enforce the
  same exclusion.
- **Reading involves HTML scraping.** Mark this in the Phase 1
  Python API: a `get_system_info()` call that scrapes
  `/configuration/system.html` belongs here even though there is
  no `get_system_info` CGI.
- **`ncidbar` refresh.** The banner (status bar at the top of every
  page) interpolates the system name (`ncidbar.html:101`:
  `text1=ProCurve Switch 2810-24G (J9021A)` — note: on this firmware
  the banner text is static, not the sysName). The form's refresh
  call is defensive; Python callers need not re-issue any banner
  GET.
