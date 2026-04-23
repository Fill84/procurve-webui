# set_port_config

**Tab:** configuration
**Kind:** write
**Source in applet:** none — HTML form only (the form served by
`/cgi/port_form`).
**Source in HTML:** `research/fixtures/get_port_form.response.txt`
(captured form body). The form element is
`<Form Name="mpf" Action="../cgi/mod_ports" onSubmit="return chkSubmit();">`.
Sub-tab key in menu: `ports` (menu.html:42). The applet param that
defines the upstream list/edit pipeline is at
`research/mirror/2026-04-23/configuration/ports1.html:34`.

## HTTP contract

- **Method:** GET (HTML `<form>` defaults to GET).
- **URL template:** `/cgi/mod_ports?indeces={ports_csv}&_portName={name}&hpSwitchPortAdminStatus={1|2}&hpSwitchPortFastEtherMode={mode}&hpSwitchPortFlowControl={1|2}&apply=+Apply+Settings+`
- **Query params:**

  | name | type | required | description |
  |---|---|---|---|
  | indeces | comma-separated port numbers | yes | Ports to apply the change to. Echoed from the form's hidden `indeces` value. Preserve misspelling. |
  | _portName | string (0-64, no `~`) | yes | Port label. Empty = clear the name. Note the leading underscore — preserve verbatim. |
  | hpSwitchPortAdminStatus | `1` or `2` | yes | `1` = admin-enabled, `2` = admin-disabled. |
  | hpSwitchPortFastEtherMode | `1`,`2`,`3`,`4`,`5`,`7`,`8`,`9`,`11` | yes | Line mode. See table below. Value `6` is not used. |
  | hpSwitchPortFlowControl | `1` or `2` | yes | `2` = enable flow control, `1` = disable. |
  | apply | literal `" Apply Settings "` | submit button value | Preserve for byte-exact replay. |

  Mode values (from the form's `<select>`):

  | value | label |
  |---|---|
  | `1` | 10HDx |
  | `2` | 100HDx |
  | `3` | 10FDx |
  | `4` | 100FDx |
  | `5` | Auto |
  | `7` | Auto-10 |
  | `8` | Auto-100 |
  | `9` | Auto-1000 (factory default on gig ports) |
  | `11` | Auto-10-100 |

  Cross-field rule enforced client-side (chkSubmit, port_form
  response lines 7-20): flow-control cannot be enabled when the
  selected mode is half-duplex (`10HDx` or `100HDx`). Python
  validation should mirror or tolerate server-side rejection.

- **Request headers:** none beyond standard.
- **Request body:** none (GET).
- **Response body:** **not live-tested.** Expected to be a short
  `OK~...` acknowledgement or a redirect back to the list view.
- **Success indicator:** HTTP 200 and subsequent `get_portscfg`
  reflecting the new values.
- **Error indicators:** Non-200 HTTP.

## Field reference

| field | wire key | wire type | python type | validation | notes |
|---|---|---|---|---|---|
| ports | `indeces` | csv ints | `list[int]` | `len >= 1` | Ports to modify. |
| name | `_portName` | string | `str` | `max_length=64`, no `~` | Empty string = clear the port name. |
| admin_enabled | `hpSwitchPortAdminStatus` | `1`/`2` | `bool` | | True → `1`, False → `2`. |
| mode | `hpSwitchPortFastEtherMode` | enum int | `PortMode` enum | value in {1,2,3,4,5,7,8,9,11} | See table above. |
| flow_control_enabled | `hpSwitchPortFlowControl` | `1`/`2` | `bool` | | True → `2`, False → `1`. |
| apply | `apply` | literal | str | exact string | Submit button value; preserve. |

## Example request

Rename port 1 to `uplink`, set to Auto-1000, flow control on:
```
GET /cgi/mod_ports?indeces=1&_portName=uplink&hpSwitchPortAdminStatus=1&hpSwitchPortFastEtherMode=9&hpSwitchPortFlowControl=2&apply=+Apply+Settings+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

Disable ports 23, 24 (bulk):
```
GET /cgi/mod_ports?indeces=23,24&_portName=&hpSwitchPortAdminStatus=2&hpSwitchPortFastEtherMode=9&hpSwitchPortFlowControl=2&apply=+Apply+Settings+ HTTP/1.1
Host: 192.168.178.3
Accept: */*
```

See `research/fixtures/<none>` — write operation, not live-tested.

## Pydantic sketch

```python
from enum import IntEnum
from pydantic import BaseModel, Field, field_validator


class PortMode(IntEnum):
    HDX_10 = 1
    HDX_100 = 2
    FDX_10 = 3
    FDX_100 = 4
    AUTO = 5
    AUTO_10 = 7
    AUTO_100 = 8
    AUTO_1000 = 9
    AUTO_10_100 = 11


class SetPortConfigRequest(BaseModel):
    ports: list[int] = Field(min_length=1)
    name: str = Field(default="", max_length=64)
    admin_enabled: bool = True
    mode: PortMode = PortMode.AUTO_1000
    flow_control_enabled: bool = True

    @field_validator("name")
    @classmethod
    def no_tilde(cls, v: str) -> str:
        if "~" in v:
            raise ValueError("port name must not contain '~'")
        return v


class SetPortConfigResponse(BaseModel):
    ok: bool
```

## Notes & caveats

- **Multi-port writes overwrite every selected port identically.**
  The UI's `Modify Selected Ports` button treats the form as a
  broadcast: every listed port gets the same name/status/mode.
  Python callers should avoid multi-port submits when the name
  field is non-empty (would clone the same label across all
  selected ports).
- **Underscore prefix in `_portName`.** Preserve verbatim — the
  switch's CGI key is `_portName`, not `portName`.
- **Empty name semantics.** Submitting `_portName=` (empty string)
  resets the port name to its default (the port number in the
  list view — see `get_portscfg.response.txt` row 4 where port 4
  shows `4-Dyn3`, implying a prior CLI-set name, vs port 18 with
  label `UPS` set via some other path). Behaviour confirmation is
  a Phase-1 live test.
- **Related:** `get_portscfg` (list), `get_port_form` (read the
  current form), `set_bobports` (enable/disable shortcut from the
  Device View tab — same end effect as
  `hpSwitchPortAdminStatus` here).
