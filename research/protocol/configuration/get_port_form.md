# get_port_form

**Tab:** configuration
**Kind:** read
**Source in applet:** `GenericList.java` / `ListPane.java:560-618`
(`submitMultipleItems()` opens
`formURL + "?indeces=" + <selected-port>` in the target frame).
The applet does not parse the response — it just navigates the
`nc_view` frame to it; the switch serves the response as a full
HTML page.
**Source in HTML:** `research/mirror/2026-04-23/configuration/ports1.html:34`
(`<param name=formURL value="../cgi/port_form">`); triggered by the
`Modify Selected Ports` button at
`research/mirror/2026-04-23/configuration/ports2.html:14-19`.
Sub-tab key in menu: `ports` (menu.html:42).

## HTTP contract

- **Method:** GET
- **URL template:** `/cgi/port_form?indeces={ports_csv}`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | comma-separated port numbers (misspelled) | yes | Ports the form should show. The UI submits only the selected ports. Comma is URL-encoded to `%2C` when sent by the applet (`ListPane.java:572`: `URLEncoder.encode(",")`); a literal `,` is also accepted. Note the misspelling — preserve verbatim on the wire. |

- **Request headers:** none beyond standard.
- **Request body:** none.
- **Response headers (relevant):** `Content-Type: text/html`
  (not observed verbatim; inferred from the HTML body).
- **Response body:** full HTML page containing a `<form>` whose
  `action` is `../cgi/mod_ports`. The form carries four editable
  fields plus a hidden `indeces` equal to the request's `indeces`.
  See `set_port_config.md` for the downstream submit contract.

  The form's field defaults are set to the *current* live values
  for the selected ports, which is why this CGI is effectively the
  per-port config read. Fields observed on the 2810 with
  `indeces=1`:
  - `<Input type=hidden name=indeces value="1">`
  - `<Input type=text name=_portName size=15 value="">`
  - `<Input type=radio name=hpSwitchPortAdminStatus value=1 Checked>` /
    `<Input type=radio name=hpSwitchPortAdminStatus value=2>`
  - `<Select name=hpSwitchPortFastEtherMode>` with options
    `1`=10HDx, `2`=100HDx, `3`=10FDx, `4`=100FDx, `5`=Auto,
    `7`=Auto-10, `8`=Auto-100, `9`=Auto-1000 (selected on port 1),
    `11`=Auto-10-100.
  - `<Select name=hpSwitchPortFlowControl>` with options
    `2`=Enable (selected), `1`=Disable.

- **Success indicator:** HTTP 200 with body containing
  `<form ... action="../cgi/mod_ports" ...>`.
- **Error indicators:** Non-200 HTTP; HTML without the expected
  form (e.g. error page).

## Field reference

Request:

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| ports | `indeces` | comma-separated int list | `list[int]` | `len >= 1` | Ports to edit. |

Response (parsed from HTML — the relevant `<input>` / `<select>`
values):

| field | HTML element | wire type | python type | notes |
|---|---|---|---|---|
| indeces | hidden input | csv ints | `list[int]` | Echoed from the request. |
| port_name | `<input name=_portName value="...">` | string | `str` | Current per-port name. Empty when unset. |
| admin_status | selected radio `hpSwitchPortAdminStatus` | `1` or `2` | `bool` | `1` = enabled, `2` = disabled. |
| mode | selected `<option>` of `hpSwitchPortFastEtherMode` | integer | enum (see `set_port_config.md`) | Configured line mode. |
| flow_control | selected `<option>` of `hpSwitchPortFlowControl` | `1` or `2` | `bool` | `2` = enable, `1` = disable. |

## Example request

Read config for port 1:
```
GET /cgi/port_form?indeces=1 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Multi-port (opens the form prefilled with shared state; fields
that differ across ports come back blank or at their default):
```
GET /cgi/port_form?indeces=1,2,3 HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

## Example response

See `research/fixtures/get_port_form.response.txt` (live-captured
2026-04-23 with `indeces=1`, 3374 bytes). This is an HTML page,
not a tilde-delimited record stream.

Excerpt (condensed):
```html
<Form Name="mpf" Action="../cgi/mod_ports" onSubmit="return chkSubmit();">
<Input Type="hidden" Name="indeces" Value="1">
...
<Input Type="text" Name="_portName" size=15 value="">
...
<Input Type="RADIO" Name="hpSwitchPortAdminStatus" Value=1 Checked> Yes
<Input Type="RADIO" Name="hpSwitchPortAdminStatus" Value=2> No
...
<Select Name="hpSwitchPortFastEtherMode" size=1>
<option value=1> 10HDx
<option value=2> 100HDx
<option value=3> 10FDx
<option value=4> 100FDx
<option value=5> Auto
<option value=7> Auto-10
<option value=8> Auto-100
<option value=9 selected> Auto-1000
<option value=11> Auto-10-100
</Select>
...
<Select Name="hpSwitchPortFlowControl" size=1>
<Option Value=2 Selected>Enable
<Option Value=1>Disable
</Select>
```

## Pydantic sketch

```python
from pydantic import BaseModel


class GetPortFormResponse(BaseModel):
    ports: list[int]  # echoed from indeces
    port_name: str | None  # "" when unset; None when mixed across ports
    admin_enabled: bool
    mode: int  # see PortMode in set_port_config.md
    flow_control_enabled: bool
    # Parsed by scraping the HTML response.
```

## Notes & caveats

- **HTML, not tilde-delimited.** Unique among Configuration-tab
  reads — this endpoint returns a full HTML page that the browser
  renders in-frame; a Python client must parse the form to get the
  current values. Use `lxml.html` or `beautifulsoup4`.
- **Mode value `6` is missing.** The options list jumps from `5`
  (Auto) to `7` (Auto-10). `6` is presumably a legacy auto-mode
  removed in this firmware; avoid emitting it.
- **Port name char restriction.** The `chkSubmit` JS (port_form
  HTML:24-44) forbids `~` in the port name (line 35-43): the `~`
  is the switch's response delimiter. Python validation must
  mirror.
- **Length limits.** Port name ≤ 64 chars (port_form:29-32);
  broadcast limit (if present) must be 0..99 (port_form:21-25).
  The 2810 does not expose a `hpSwitchPortBcastLimit` input in the
  observed response, so the broadcast-limit check is defensive.
- **Related:** `get_portscfg` (the list view) and
  `set_port_config` (the write target of this form).
